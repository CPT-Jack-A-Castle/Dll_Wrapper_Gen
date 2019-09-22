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
architecture = 'Unknown'
p = sub.Popen(f'dumpbin_tools\\dumpbin.exe /headers "{dllPath}"', stdout=sub.PIPE, stderr=sub.PIPE)
output, errors = p.communicate()
output = output.decode('utf-8')

if 'x86' in output:
    print('x86 dll detected ...')
    architecture = 'x86'
elif 'x64' in output:
    print('x64 dll detected ...')
    architecture = 'x64'
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
    if start is 1:
        start = 2
        continue
    if start is 2:
        if len(line) is 0:
            break
        split = re.compile(r"(\s+)").split(line.strip())

        if len(split) > 3 and split[6] == "(forwarded":
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
proxyFuncName = "MFSX"

dllProxyName = dllName.replace('.dll', '')
dllProxyFolder = f"{dllProxyName}\\{dllProxyName}"

templateFolder = f'Visual Studio Project Template\\{architecture}\\'
templateProjectName = "MyName"
templateProjectFolder = f'{templateFolder}\\{templateProjectName}'
templateProjectFiles = (f'{templateFolder}\\{templateProjectName}.sln',
                        f'{templateProjectFolder}\\{templateProjectName}.vcxproj',
                        f'{templateProjectFolder}\\{templateProjectName}.vcxproj.filters')

dllProxyProjectFiles = (f'{dllProxyName}\\{dllProxyName}.sln',
                        f'{dllProxyFolder}\\{dllProxyName}.vcxproj',
                        f'{dllProxyFolder}\\{dllProxyName}.vcxproj.filters')

dllProxyFiles = [f'{dllProxyName}.cpp', f'{dllProxyName}.def']

if architecture == 'x64':
    dllProxyFiles.append(f'{dllProxyName}_asm.asm')

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
    f.write('#include <windows.h>\n#include <tchar.h>\n\n')
    f.write('HINSTANCE mHinstDLL = 0;\n')

    if architecture == 'x64':  # For X64
        f.write('extern \"C\" ')

    f.write(f'UINT_PTR mProcs[{str(len(LoadNames))}] = {{ 0 }};\n\n')
    f.write('LPCSTR mImportNames[] = { ')
    for idx, val in enumerate(LoadNames):
        if idx is not 0:
            f.write(', ')
        f.write(val)
    f.write(' };\n\n')
    f.write(f'void {proxyFuncName}();\n\n')
    f.write('BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved) {\n')
    f.write('\tif (fdwReason == DLL_PROCESS_ATTACH) {\n')
    f.write('\t\tTCHAR szPath[MAX_PATH];\n\n')
    f.write('\t\tif (!GetSystemDirectory(szPath, MAX_PATH))\n')
    f.write('\t\t\treturn FALSE;\n\n')
    f.write(f'\t\t_tcscat_s(szPath, _T(\"\\\\{dllName}\"));\n\n')
    f.write('\t\tmHinstDLL = LoadLibrary(szPath);\n\n')
    f.write('\t\tif (!mHinstDLL)\n')
    f.write('\t\t\treturn FALSE;\n\n')
    f.write(f'\t\tfor (int i = 0; i < {str(len(LoadNames))}; i++)\n')
    f.write('\t\t\tmProcs[i] = (UINT_PTR)GetProcAddress(mHinstDLL, mImportNames[i]);\n\n')
    f.write(f'\t\tCreateThread(0, 0, (LPTHREAD_START_ROUTINE){proxyFuncName}, 0, 0, NULL);\n')
    f.write('\t}\n\telse if (fdwReason == DLL_PROCESS_DETACH) {\n')
    f.write('\t\tFreeLibrary(mHinstDLL);\n')
    f.write('\t}\n\n')
    f.write('\treturn TRUE;\n')
    f.write('}\n\n')
    f.write(f'void {proxyFuncName}() {{\n')
    f.write('\tMessageBox(NULL, _T("Hello World!"), _T("Hi"), NULL);\n')
    f.write('}\n\n')

    if architecture == 'x64':
        for item in WrapFcn:
            f.write(f'extern \"C\" void {item}();\n')
    else:
        for idx, item in enumerate(WrapFcn):
            f.write(
                f'extern \"C\" __declspec(naked) void __stdcall {item}(){{ __asm {{ jmp mProcs[{str(idx)} * 4] }} }}\n')

# Generate ASM File
print('Generating .asm file')
if architecture == 'x86':
    print('x86 wrapper will use inline asm.')
else:
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
if architecture == 'x64':
    shutil.move(dllProxyFiles[2], dllProxyFolder)
