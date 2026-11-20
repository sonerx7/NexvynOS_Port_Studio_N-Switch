param(
    [string]$OutputFile = "screenshots/latest.png"
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$csharpSource = @'
using System;
using System.Text;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Collections.Generic;

public class ScreenGrabber {
    [DllImport("user32.dll")]
    private static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
    private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
    private static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

    [DllImport("user32.dll")]
    private static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll")]
    private static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll")]
    private static extern bool SetForegroundWindow(IntPtr hWnd);

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    public static bool CaptureWindowOrScreen(string targetTitleSubstring, string outputPath) {
        IntPtr foundHwnd = IntPtr.Zero;
        string foundTitle = "";

        EnumWindows((hWnd, lParam) => {
            if (!IsWindowVisible(hWnd)) return true;
            StringBuilder sb = new StringBuilder(256);
            GetWindowText(hWnd, sb, 256);
            string title = sb.ToString();
            if (!string.IsNullOrEmpty(title) && title.IndexOf(targetTitleSubstring, StringComparison.OrdinalIgnoreCase) >= 0) {
                foundHwnd = hWnd;
                foundTitle = title;
                return false;
            }
            return true;
        }, IntPtr.Zero);

        if (foundHwnd != IntPtr.Zero) {
            SetForegroundWindow(foundHwnd);
            System.Threading.Thread.Sleep(300);

            RECT r;
            GetWindowRect(foundHwnd, out r);
            int w = r.Right - r.Left;
            int h = r.Bottom - r.Top;
            if (w > 100 && h > 100) {
                using (Bitmap bmp = new Bitmap(w, h)) {
                    using (Graphics g = Graphics.FromImage(bmp)) {
                        g.CopyFromScreen(r.Left, r.Top, 0, 0, new Size(w, h));
                    }
                    bmp.Save(outputPath, ImageFormat.Png);
                }
                Console.WriteLine("Pencere yakalandi: " + foundTitle + " (" + w + "x" + h + ")");
                return true;
            }
        }

        // Bulunamazsa tüm ekranı al
        Rectangle bounds = System.Windows.Forms.Screen.PrimaryScreen.Bounds;
        using (Bitmap bmp = new Bitmap(bounds.Width, bounds.Height)) {
            using (Graphics g = Graphics.FromImage(bmp)) {
                g.CopyFromScreen(bounds.Left, bounds.Top, 0, 0, bounds.Size);
            }
            bmp.Save(outputPath, ImageFormat.Png);
        }
        Console.WriteLine("Tum ekran yakalandi (" + bounds.Width + "x" + bounds.Height + ")");
        return true;
    }
}
'@

Add-Type -TypeDefinition $csharpSource -ReferencedAssemblies System.Windows.Forms, System.Drawing -ErrorAction SilentlyContinue

$dir = Split-Path $OutputFile -Parent
if ($dir -and -not (Test-Path $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}

[ScreenGrabber]::CaptureWindowOrScreen("Ryujinx", $OutputFile)
