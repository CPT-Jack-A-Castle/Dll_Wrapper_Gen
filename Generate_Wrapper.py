import os
import re
import shutil
import subprocess as sub
import sys
import time

# Info
print('Wrapper Generator. Copyright © Lin Min (Modified by Mobile46)')

# Check args
if len(sys.argv) < 2:
    print('You should pass a dll file to this program!')
    sys.exit(1)
    
# Get the input parameter first.
dllPath = os.path.realpath(sys.argv[1])
dllName = os.path.basename(dllPath)

# Check whether is a dll file.
if not dllName.endswith('.dll'):
    print('You should pass a dll file to this program!')
    sys.exit(1)

# Check whether the dll file specified exists.
if os.path.exists(dllPath):
    print('#############################')
    print('Reading dll file ...')
else:
    print(f'The Specified file \"{dllPath}\" does not exist!')
    sys.exit(1)

# Check Architecture
p = sub.Popen(f'dumpbin_tools\\dumpbin.exe /headers "{dllPath}"', stdout=sub.PIPE, stderr=sub.PIPE)
output, errors = p.communicate()
output = output.decode('utf-8')

if 'x86' in output:
    print('x86 dll detected ...')
elif 'x64' in output:
    print('x64 dll detected ...')
else:
    print('invalid dll file, exiting ...')
    sys.exit(1)

# Get Export List
p = sub.Popen(f'dumpbin_tools\\dumpbin.exe /exports "{dllPath}"', stdout=sub.PIPE, stderr=sub.PIPE)
output, errors = p.communicate()
output = output.decode('utf-8')
lines = output.split('\r\n')
start = 0
idx1 = 0
idx2 = 0
idx3 = 0
idx4 = 0
LoadNames = []
WrapFcn = []
DefItem = []
for line in lines:
    if 'ordinal' in line and 'hint' in line and 'RVA' in line and 'name' in line:
        start = 1
        idx1 = line.find('ordinal')
        idx2 = line.find('hint')
        idx3 = line.find('RVA')
        idx4 = line.find('name')
        continue
    if start == 1:
        start = 2
        continue
    if start == 2:
        if len(line) == 0:
            break
        split = re.compile(r'(\s+)').split(line.strip())

        if len(split) > 3 and split[6] == '(forwarded':
            split = split[:-6]

        ordinal = split[0]
        funcName = split[-1]

        if funcName == '[NONAME]':
            LoadNames.append(f'(LPCSTR){ordinal}')
            WrapFcn.append(f'ExportByOrdinal{ordinal}')
            DefItem.append(f'ExportByOrdinal{ordinal} @{ordinal} NONAME')
        else:
            LoadNames.append(f'\"{funcName}\"')
            WrapFcn.append(f'{funcName}_proxy')
            DefItem.append(f'{funcName}={funcName}_proxy @{ordinal}')

# Variables
proxyFuncName = 'MFSX'

dllProxyName = dllName.replace('.dll', '')
dllProxyFolder = f'{dllProxyName}\\{dllProxyName}'

templateFolder = f'Visual Studio Project Template\\'
templateProjectName = 'MyName'
templateProjectFolder = f'{templateFolder}\\{templateProjectName}'
templateProjectFiles = (f'{templateFolder}\\{templateProjectName}.sln',
                        f'{templateProjectFolder}\\{templateProjectName}.vcxproj',
                        f'{templateProjectFolder}\\{templateProjectName}.vcxproj.filters')

dllProxyProjectFiles = (f'{dllProxyName}\\{dllProxyName}.sln',
                        f'{dllProxyFolder}\\{dllProxyName}.vcxproj',
                        f'{dllProxyFolder}\\{dllProxyName}.vcxproj.filters')

dllProxyFiles = [f'{dllProxyName}.cpp', f'{dllProxyName}.def', f'{dllProxyName}_asm.asm']

# Generate Def File
print('Generating .def file')

with open(dllProxyFiles[1], 'w') as f:
    f.write(f'LIBRARY {dllName}\n')
    f.write('EXPORTS\n')
    for item in DefItem:
        f.write(f'{item}\n')

# Generate CPP File
print('Generating .cpp file')

with open(dllProxyFiles[0], 'w') as f:
    f.write('#include <Windows.h>\n\n')
    f.write('HINSTANCE mHinstDLL = nullptr;\n')
    f.write('#ifdef _WIN64\nextern \"C\"\n#endif\n')

    f.write(f'uintptr_t mProcs[{str(len(LoadNames))}] = {{ 0 }};\n\n')
    f.write('const char* mImportNames[] = { ')
    for idx, val in enumerate(LoadNames):
        if idx != 0:
            f.write(', ')
        f.write(val)
    f.write(' };\n\n')
    f.write(f'void {proxyFuncName}();\n\n')
    f.write('BOOL APIENTRY DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved) {\n')
    f.write('\tif (fdwReason == DLL_PROCESS_ATTACH) {\n')
    f.write('\t\tchar szPath[MAX_PATH];\n\n')
    f.write('\t\tif (!GetSystemDirectory(szPath, MAX_PATH))\n')
    f.write('\t\t\treturn false;\n\n')
    f.write(f'\t\tstrcat_s(szPath, \"\\\\{dllName}\");\n\n')
    f.write('\t\tmHinstDLL = LoadLibrary(szPath);\n\n')
    f.write('\t\tif (!mHinstDLL)\n')
    f.write('\t\t\treturn false;\n\n')
    f.write(f'\t\tfor (int i = 0; i < {str(len(LoadNames))}; i++)\n')
    f.write('\t\t\tmProcs[i] = reinterpret_cast<uintptr_t>(GetProcAddress(mHinstDLL, mImportNames[i]));\n\n')
    f.write(f'\t\tCreateThread(nullptr, 0, reinterpret_cast<LPTHREAD_START_ROUTINE>({proxyFuncName}),'
            f' nullptr, 0, nullptr);\n')
    f.write('\t}\n\telse if (fdwReason == DLL_PROCESS_DETACH) {\n')
    f.write('\t\tFreeLibrary(mHinstDLL);\n')
    f.write('\t}\n\n')
    f.write('\treturn true;\n')
    f.write('}\n\n')
    f.write(f'void {proxyFuncName}() {{\n')
    f.write('\tMessageBox(nullptr, "Hello World!", "Hi", 0);\n')
    f.write('}\n\n')

    f.write('extern \"C\" {\n')
    f.write('#ifdef _WIN64\n')
    for item in WrapFcn:
        f.write(f'void {item}();\n')
    f.write('#else\n')
    for idx, item in enumerate(WrapFcn):
        f.write(f'__declspec(naked) void __stdcall {item}(){{ __asm {{ jmp mProcs[{str(idx)} * 4] }} }}\n')
    f.write('#endif\n}')

# Generate ASM File
print('Generating .asm file')
with open(dllProxyFiles[2], 'w') as f:
    f.write('.code\nextern mProcs:QWORD\n')
    for idx, item in enumerate(WrapFcn):
        f.write(f'{item} proc\n\tjmp mProcs[{str(idx)}*8]\n{item} endp\n')
    f.write('end\n')

# Generate MS Visual Studio Project Files.
if os.path.exists(dllProxyName):
    shutil.rmtree(dllProxyName)
time.sleep(2)
os.mkdir(dllProxyName)
os.mkdir(dllProxyFolder)

# Generate Project Files
i = 0
for file in templateProjectFiles:
    with open(file, 'r') as templateFile:
        with open(dllProxyProjectFiles[i], 'w') as projectFile:
            for line in templateFile:
                line = line.replace('MyName', dllProxyName)
                line = line.replace('MYNAME', dllProxyName.upper())
                projectFile.write(line)
            i = i + 1

shutil.move(dllProxyFiles[0], dllProxyFolder)
shutil.move(dllProxyFiles[1], dllProxyFolder)
shutil.move(dllProxyFiles[2], dllProxyFolder)
