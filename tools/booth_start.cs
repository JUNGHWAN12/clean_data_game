// 부스 시작(START_BOOTH.exe): Booth 폴더 맨 위에서 더블클릭하면 부스 런처를 켠다.
//
// 학생들이 CleanDataLabeler 폴더 안의 run_booth.bat을 찾지 않아도 되도록, run_booth.bat과 같은 일을 한다.
// - CleanDataLabeler 폴더에 booth.json이 있으면 런처(--launcher), 없으면 클린 데이터 라벨러만 켠다.
// - 진행 요원이 Ctrl+Shift+Q로 끄면(종료 코드 0) 끝낸다.
// - card.json 형식 오류(종료 코드 3)는 다시 켜도 같으므로 안내 창을 띄우고 끝낸다.
// - 그 밖의 오류로 꺼지면 3초 뒤 다시 켠다. 켜자마자 꺼지는 일이 5번 이어지면 안내 창을 띄우고 멈춘다.
// - START_BOOTH.exe --check: 게임을 켜지 않고 CleanDataLabeler.exe --check 결과(0/1)를 돌려준다(빌드 점검용).
//
// PyInstaller 한 파일(onefile) 실행 파일은 켤 때마다 묶인 파일을 임시 폴더로 꺼내는데, 백신이 막 받은
// 실행 파일을 잠그면 "Failed to extract ...: failed to open archive file!"로 켜지지 않았다.
// 그래서 Windows에 기본으로 들어 있는 .NET Framework로 만든다. 꺼낼 파일이 없고 크기도 수십 KB다.
//
// 빌드(Windows): C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /nologo /target:winexe
//   /codepage:65001 /out:START_BOOTH.exe tools\booth_start.cs
using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Forms;

static class BoothStart
{
    const string Title = "부스 시작";
    const int CardErrorExit = 3;          // main.py의 CARD_ERROR_EXIT와 같다
    const int RestartDelayMs = 3000;
    const double QuickCrashSeconds = 20;  // 켠 뒤 이 시간 안에 오류로 꺼지면 '켜자마자 꺼짐'으로 센다
    const int MaxQuickCrashes = 5;

    [DllImport("user32.dll")]
    static extern bool AllowSetForegroundWindow(int processId);
    const int ASFW_ANY = -1;

    static void Message(string text)
    {
        MessageBox.Show(text, Title, MessageBoxButtons.OK, MessageBoxIcon.Error);
    }

    static int Run(string game, string arguments, string folder)
    {
        var info = new ProcessStartInfo(game, arguments);
        info.WorkingDirectory = folder;
        info.UseShellExecute = false;
        using (var process = Process.Start(info))
        {
            process.WaitForExit();
            return process.ExitCode;
        }
    }

    [STAThread]
    static int Main(string[] args)
    {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string folder = Path.Combine(root, "CleanDataLabeler");
        string game = Path.Combine(folder, "CleanDataLabeler.exe");
        if (!File.Exists(game))
        {
            Message("게임을 찾지 못했습니다.\n\n이 파일과 같은 폴더에 CleanDataLabeler 폴더가 있어야 합니다.\n찾은 위치: " + game);
            return 1;
        }
        if (args.Length > 0 && args[0] == "--check")
        {
            return Run(game, "--check", folder);
        }
        string arguments = File.Exists(Path.Combine(folder, "booth.json")) ? "--launcher" : "";
        // 창이 없는 이 프로그램 대신, 곧 켜질 런처 창이 화면 맨 앞으로 나올 수 있게 허락한다.
        AllowSetForegroundWindow(ASFW_ANY);
        int quickCrashes = 0;
        while (true)
        {
            var timer = Stopwatch.StartNew();
            int code;
            try
            {
                code = Run(game, arguments, folder);
            }
            catch (Exception error)
            {
                Message("게임을 실행하지 못했습니다.\n\n" + error.Message);
                return 1;
            }
            if (code == 0)
            {
                return 0;
            }
            if (code == CardErrorExit)
            {
                Message("card.json 형식이 올바르지 않아 게임을 시작할 수 없습니다.\n\n" +
                        "CleanDataLabeler 폴더의 error.log에서 몇 번째 카드가 문제인지 확인해 고친 뒤 다시 실행하세요.");
                return CardErrorExit;
            }
            quickCrashes = timer.Elapsed.TotalSeconds < QuickCrashSeconds ? quickCrashes + 1 : 0;
            if (quickCrashes >= MaxQuickCrashes)
            {
                Message("게임이 켜자마자 계속 꺼집니다.\n\nCleanDataLabeler 폴더의 error.log를 확인하고 진행 요원(선생님)에게 알려 주세요.");
                return code;
            }
            Thread.Sleep(RestartDelayMs);
            AllowSetForegroundWindow(ASFW_ANY);
        }
    }
}
