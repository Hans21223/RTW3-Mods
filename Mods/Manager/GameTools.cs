using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Windows.Forms;

// Companion UI, not a replacement for any native RTW3 toolbar button.
// It is visible only while the bound game or its live-cheat window is active.
internal sealed class GameToolsHost : Form
{
    [DllImport("user32.dll")] private static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr window, out uint pid);
    [DllImport("user32.dll")] private static extern bool RegisterHotKey(IntPtr window, int id, uint modifiers, uint key);
    [DllImport("user32.dll")] private static extern bool UnregisterHotKey(IntPtr window, int id);
    private readonly int gamePid;
    private readonly string root = AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
    private readonly Timer timer = new Timer { Interval = 150 };
    private readonly Button cheats;
    private readonly Label researchLabel;
    private readonly ProgressBar researchBar;
    private bool progressBusy;
    private DateTime nextProgress = DateTime.MinValue;
    private bool registered;
    private Form menu;

    internal GameToolsHost(int pid, bool previewMode = false)
    {
        gamePid = pid;
        Text = "RTW3 campaign tools"; ShowInTaskbar = false; TopMost = true;
        FormBorderStyle = FormBorderStyle.FixedToolWindow;
        MaximizeBox = false; MinimizeBox = false;
        ClientSize = new Size(245, 87); StartPosition = FormStartPosition.Manual;
        Location = new Point(Screen.PrimaryScreen.WorkingArea.Right-275, Screen.PrimaryScreen.WorkingArea.Top+45);
        BackColor = Color.FromArgb(18, 26, 35);
        cheats = new Button { Dock = DockStyle.Top, Height = 39, Text = "CHEATS  /  F10", FlatStyle = FlatStyle.Flat,
                              BackColor = Color.FromArgb(33, 131, 130), ForeColor = Color.White,
                              Font = new Font("Segoe UI", 10, FontStyle.Bold) };
        researchLabel = new Label { Dock = DockStyle.Fill, Text = "Technology progress - load campaign", ForeColor = Color.White, TextAlign = ContentAlignment.MiddleCenter };
        researchBar = new ProgressBar { Dock = DockStyle.Bottom, Height = 16 };
        Controls.Add(researchLabel); Controls.Add(researchBar);
        cheats.Click += delegate { OpenMenu(); }; Controls.Add(cheats);
        timer.Tick += delegate { Tick(); };
        if (!previewMode) Shown += delegate { Hide(); timer.Start(); };
        FormClosed += delegate { timer.Stop(); timer.Dispose(); if (registered) UnregisterHotKey(Handle, 10); if (menu != null) menu.Close(); };
    }

    protected override bool ShowWithoutActivation { get { return true; } }

    internal static void RenderPreview(string path)
    {
        using (GameToolsHost host = new GameToolsHost(0, true)) {
            host.Opacity = 0;
            host.Show(); host.PerformLayout();
            if (!host.cheats.Visible || host.cheats.Width < 190) throw new Exception("In-game cheat launcher did not lay out.");
            using (Bitmap capture = new Bitmap(host.Width, host.Height)) {
                host.DrawToBitmap(capture, new Rectangle(Point.Empty, host.Size));
                capture.Save(path, System.Drawing.Imaging.ImageFormat.Png);
            }
            host.Hide();
        }
    }

    private void Tick()
    {
        try { using (Process process = Process.GetProcessById(gamePid)) if (process.HasExited) { Close(); return; } }
        catch (ArgumentException) { Close(); return; }
        uint foregroundPid; GetWindowThreadProcessId(GetForegroundWindow(), out foregroundPid);
        bool active = foregroundPid == (uint)gamePid || (menu != null && menu.Visible && menu.ContainsFocus);
        if (active && !Visible) Show();
        if (!active && Visible) Hide();
        if (active && !registered) {
            registered = RegisterHotKey(Handle, 10, 0x4000, (uint)Keys.F10);
            cheats.Text = registered ? "CHEATS  /  F10" : "CHEATS  /  CLICK";
        }
        if (!active && registered) { UnregisterHotKey(Handle, 10); registered = false; }
        if (active && !progressBusy && DateTime.UtcNow >= nextProgress) UpdateResearchProgress();
    }

    private async void UpdateResearchProgress()
    {
        progressBusy = true; nextProgress = DateTime.UtcNow.AddSeconds(8);
        try {
            var result = await ManagerWindow.CallBackendAt(root, "live-progress", "--pid", gamePid.ToString());
            if (IsDisposed || Disposing) return;
            var data = (System.Collections.Generic.Dictionary<string, object>)result["research_progress"];
            if ((bool)data["available"]) {
                researchBar.Value = Convert.ToInt32(data["percent"]);
                researchLabel.Text = "Tech: " + data["completed"] + " / " + data["total"] + "  (" + data["percent"] + "%)";
            } else { researchBar.Value = 0; researchLabel.Text = "Technology progress - load campaign"; }
        } catch { if (!IsDisposed) researchLabel.Text = "Technology progress - refresh F10"; }
        finally { progressBusy = false; }
    }

    private async void OpenMenu()
    {
        if (menu != null && !menu.IsDisposed) { menu.Show(); menu.Activate(); return; }
        menu = new Form { Text = "RTW3 Live Cheats", Size = new Size(795, 865), MinimumSize = new Size(730, 710),
                          StartPosition = FormStartPosition.CenterScreen, BackColor = BackColor };
        CampaignEditorPanel editor = new CampaignEditorPanel(args => ManagerWindow.CallBackendAt(root, args), true, false);
        menu.Controls.Add(editor);
        menu.Show(); menu.Activate();
        menu.FormClosing += delegate(object sender, FormClosingEventArgs e) { if (editor.IsBusy) e.Cancel = true; };
        await editor.InitializeAsync(true);
    }

    protected override void WndProc(ref Message message)
    {
        if (message.Msg == 0x312 && message.WParam.ToInt32() == 10) { OpenMenu(); return; }
        base.WndProc(ref message);
    }
}
