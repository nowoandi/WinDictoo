# Screenshot a top-level window by title substring to a PNG.
# Usage: powershell -File shot.ps1 -Title "WinDictoo" -Out shot.png
param([string]$Title = "WinDictoo", [string]$Out = "shot.png")
Add-Type @"
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public class Win {
  public struct RECT { public int Left, Top, Right, Bottom; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr h);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  public static IntPtr Find(string sub) {
    IntPtr exact = IntPtr.Zero; long exactArea = 0;
    IntPtr sub2 = IntPtr.Zero; long subArea = 0;
    EnumWindows((h, l) => {
      if (!IsWindowVisible(h)) return true;
      int len = GetWindowTextLength(h);
      if (len == 0) return true;
      var sb = new StringBuilder(len + 1);
      GetWindowText(h, sb, sb.Capacity);
      string t = sb.ToString();
      RECT r; GetWindowRect(h, out r);
      long area = (long)(r.Right - r.Left) * (r.Bottom - r.Top);
      if (t == sub) { if (area > exactArea) { exactArea = area; exact = h; } }
      else if (t.Contains(sub)) { if (area > subArea) { subArea = area; sub2 = h; } }
      return true;
    }, IntPtr.Zero);
    return exact != IntPtr.Zero ? exact : sub2;
  }
}
"@
Add-Type -AssemblyName System.Drawing

$h = [Win]::Find($Title)
if ($h -eq [IntPtr]::Zero) { Write-Output "NO WINDOW: $Title"; exit 1 }
[Win]::ShowWindow($h, 9) | Out-Null   # SW_RESTORE
# Force above other windows without needing foreground rights.
$TOPMOST = New-Object IntPtr(-1)
[Win]::SetWindowPos($h, $TOPMOST, 0,0,0,0, 0x0001 -bor 0x0002 -bor 0x0040) | Out-Null # NOSIZE|NOMOVE|SHOWWINDOW
[Win]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 600
$r = New-Object Win+RECT
[Win]::GetWindowRect($h, [ref]$r) | Out-Null
$w = $r.Right - $r.Left
$ht = $r.Bottom - $r.Top
Write-Output "RECT $($r.Left),$($r.Top) => $w x $ht"
if ($w -le 0 -or $ht -le 0) { Write-Output "BAD RECT"; exit 1 }
$bmp = New-Object System.Drawing.Bitmap $w, $ht
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($r.Left, $r.Top, 0, 0, (New-Object System.Drawing.Size $w, $ht))
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Output "SAVED $Out ($w x $ht)"
