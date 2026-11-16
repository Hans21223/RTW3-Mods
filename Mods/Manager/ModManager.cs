using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

internal static class Program
{
    [STAThread]
    private static void Main(string[] args)
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        if (args.Contains("--game-tools")) {
            int index = Array.IndexOf(args, "--pid"), pid;
            if (index < 0 || index+1 >= args.Length || !Int32.TryParse(args[index+1], out pid)) return;
            Application.Run(new GameToolsHost(pid)); return;
        }
        Application.Run(new ManagerWindow(args.Contains("--self-test"), args.Contains("--weekly-profile"), args.Contains("--save-editor")));
    }
}

internal sealed class ManagerWindow : Form
{
    private readonly string game = AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
    private readonly JavaScriptSerializer json = new JavaScriptSerializer { MaxJsonLength = 16 * 1024 * 1024 };
    private readonly Color bg = Color.FromArgb(18, 26, 35);
    private readonly Color panel = Color.FromArgb(27, 38, 50);
    private readonly Color ink = Color.FromArgb(229, 236, 243);
    private readonly Color muted = Color.FromArgb(155, 174, 191);
    private ListView mods;
    private ComboBox profiles;
    private RichTextBox detail;
    private Label statusLabel;
    private Label summary;
    private Label buildLabel;
    private ProgressBar progress;
    private FlowLayoutPanel actions;
    private ContextMenuStrip moreMenu;
    private readonly List<Button> allButtons = new List<Button>();
    private bool loading;
    private bool busy;
    private bool pending;
    private Dictionary<string, object> current;
    private readonly bool selfTest;
    private readonly bool weeklyProfile;
    private readonly bool openEditor;
    private TabControl pages;
    private CampaignEditorPanel liveEditor, saveEditor;
    private AdvancedSaveEditor advancedEditor;
    private TabControl savePages;

    internal ManagerWindow(bool runSelfTest, bool selectWeekly, bool selectEditor)
    {
        selfTest = runSelfTest;
        weeklyProfile = selectWeekly;
        openEditor = selectEditor;
        Text = "RTW3 Mod Manager and Save Editor";
        Size = new Size(1080, 790);
        MinimumSize = new Size(940, 650);
        StartPosition = FormStartPosition.CenterScreen;
        Font = new Font("Segoe UI", 10F);
        BackColor = bg;
        ForeColor = ink;
        AutoScaleMode = AutoScaleMode.Dpi;
        BuildUI();
        if (selfTest) { ShowInTaskbar = false; Opacity = 0; }
        Shown += async delegate {
            await RefreshStatus(true);
            if (weeklyProfile && current != null) profiles.SelectedIndex = 1;
            if (openEditor) pages.SelectedIndex = 2;
            if (selfTest) await RunSelfTest();
        };
        FormClosing += delegate(object sender, FormClosingEventArgs e) { if (busy || liveEditor.IsBusy || saveEditor.IsBusy || advancedEditor.IsBusy) { e.Cancel = true; statusLabel.Text = "Wait for the current operation to finish."; } };
    }

    private void BuildUI()
    {
        pages = new TabControl { Dock = DockStyle.Fill, DrawMode = TabDrawMode.OwnerDrawFixed, SizeMode = TabSizeMode.Fixed, ItemSize = new Size(170, 36), Padding = new Point(12, 4) };
        TabPage modsPage = new TabPage("Mods") { BackColor = bg };
        TabPage livePage = new TabPage("Live cheats (F10)") { BackColor = bg };
        TabPage savePage = new TabPage("Save editor") { BackColor = bg };
        pages.TabPages.AddRange(new[] { modsPage, livePage, savePage });
        pages.DrawItem += delegate(object sender, DrawItemEventArgs e) {
            bool selected = e.Index == pages.SelectedIndex;
            using (SolidBrush fill = new SolidBrush(selected ? Color.FromArgb(33, 131, 130) : panel)) e.Graphics.FillRectangle(fill, e.Bounds);
            using (Font tabFont = new Font("Segoe UI Semibold", 10)) TextRenderer.DrawText(e.Graphics, pages.TabPages[e.Index].Text, tabFont, e.Bounds, selected ? ink : muted, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPrefix);
        };
        Controls.Add(pages);
        liveEditor = new CampaignEditorPanel(args => CallBackend(args), true, selfTest);
        saveEditor = new CampaignEditorPanel(args => CallBackend(args), false, selfTest);
        livePage.Controls.Add(liveEditor);
        savePages = new TabControl { Dock = DockStyle.Fill };
        TabPage quickSave = new TabPage("Quick controls") { BackColor = bg }, advancedSave = new TabPage("Advanced fields") { BackColor = bg };
        quickSave.Controls.Add(saveEditor);
        advancedEditor = new AdvancedSaveEditor(args => CallBackend(args), selfTest);
        advancedSave.Controls.Add(advancedEditor);
        savePages.TabPages.AddRange(new[] { quickSave, advancedSave }); savePage.Controls.Add(savePages);
        savePages.SelectedIndexChanged += async delegate { if (!selfTest && savePages.SelectedIndex == 1) await advancedEditor.InitializeAsync(true); };
        TableLayoutPanel root = new TableLayoutPanel();
        root.Dock = DockStyle.Fill;
        root.Padding = new Padding(24, 18, 24, 18);
        root.ColumnCount = 1;
        root.RowCount = 6;
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 62));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 46));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 58));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 28));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 6));
        modsPage.Controls.Add(root);

        Panel header = new Panel { Dock = DockStyle.Fill };
        Label title = new Label { Text = "Rule the Waves 3", Font = new Font("Segoe UI Semibold", 18), AutoSize = true, ForeColor = ink, Location = new Point(0, 0) };
        Label subtitle = new Label { Text = "Mods, campaign loader and save tools", Font = new Font("Segoe UI", 9.5F), ForeColor = muted, AutoSize = true, Location = new Point(2, 36) };
        buildLabel = new Label { Text = "Checking local installation...", AutoSize = true, ForeColor = muted, Anchor = AnchorStyles.Top | AnchorStyles.Right, Location = new Point(680, 12) };
        header.Controls.Add(title); header.Controls.Add(subtitle); header.Controls.Add(buildLabel);
        root.Controls.Add(header, 0, 0);

        FlowLayoutPanel profileBar = new FlowLayoutPanel { Dock = DockStyle.Fill, WrapContents = false, Padding = new Padding(0, 4, 0, 0) };
        profileBar.Controls.Add(new Label { Text = "Profile", AutoSize = true, Margin = new Padding(0, 6, 12, 0), ForeColor = muted });
        profiles = new ComboBox { Width = 285, DropDownStyle = ComboBoxStyle.DropDownList, FlatStyle = FlatStyle.Flat, BackColor = panel, ForeColor = ink, DrawMode = DrawMode.OwnerDrawFixed, ItemHeight = 20 };
        profiles.DrawItem += delegate(object sender, DrawItemEventArgs e) {
            bool hot = (e.State & DrawItemState.Selected) != 0 && (e.State & DrawItemState.ComboBoxEdit) == 0;
            using (SolidBrush fill = new SolidBrush(hot ? Color.FromArgb(36, 66, 78) : panel)) e.Graphics.FillRectangle(fill, e.Bounds);
            if (e.Index >= 0) TextRenderer.DrawText(e.Graphics, profiles.Items[e.Index].ToString(), profiles.Font, new Rectangle(e.Bounds.X + 4, e.Bounds.Y, e.Bounds.Width - 4, e.Bounds.Height), ink, TextFormatFlags.VerticalCenter | TextFormatFlags.NoPrefix);
        };
        profiles.Items.AddRange(new object[] { "Event campaign (recommended)", "Weekly experiment + events", "No mods", "Custom selection" });
        profiles.SelectedIndexChanged += ProfileChanged;
        profileBar.Controls.Add(profiles);
        root.Controls.Add(profileBar, 0, 1);

        SplitContainer split = new SplitContainer { Size = new Size(1000, 400), Dock = DockStyle.Fill, SplitterDistance = 585, BackColor = bg, SplitterWidth = 16, Panel1MinSize = 430, Panel2MinSize = 260 };
        mods = new ListView { Dock = DockStyle.Fill, View = View.Details, CheckBoxes = true, FullRowSelect = true, HideSelection = false, MultiSelect = false, BackColor = panel, ForeColor = ink, BorderStyle = BorderStyle.None, HeaderStyle = ColumnHeaderStyle.Nonclickable, OwnerDraw = true };
        mods.Columns.Add("Mod", 400);
        mods.Columns.Add("Status", 104);
        Font headerFont = new Font("Segoe UI Semibold", 9);
        mods.DrawColumnHeader += delegate(object sender, DrawListViewColumnHeaderEventArgs e) {
            using (SolidBrush fill = new SolidBrush(Color.FromArgb(22, 31, 42))) e.Graphics.FillRectangle(fill, e.Bounds);
            TextRenderer.DrawText(e.Graphics, e.Header.Text, headerFont, new Rectangle(e.Bounds.X + 6, e.Bounds.Y, e.Bounds.Width - 6, e.Bounds.Height), muted, TextFormatFlags.VerticalCenter | TextFormatFlags.NoPrefix);
        };
        mods.DrawItem += delegate(object sender, DrawListViewItemEventArgs e) { };   // rows are painted per column below
        mods.DrawSubItem += delegate(object sender, DrawListViewSubItemEventArgs e) {
            using (SolidBrush fill = new SolidBrush(e.Item.Selected ? Color.FromArgb(36, 66, 78) : panel)) e.Graphics.FillRectangle(fill, e.Bounds);
            Rectangle text = new Rectangle(e.Bounds.X + 6, e.Bounds.Y, e.Bounds.Width - 6, e.Bounds.Height);
            Color color = e.ColumnIndex == 0 ? e.Item.ForeColor : e.SubItem.Text == "Off" ? muted : Color.FromArgb(91, 192, 187);
            if (e.ColumnIndex == 0) {
                CheckBoxRenderer.DrawCheckBox(e.Graphics, new Point(e.Bounds.X + 4, e.Bounds.Y + (e.Bounds.Height - 13) / 2),
                    e.Item.Checked ? System.Windows.Forms.VisualStyles.CheckBoxState.CheckedNormal : System.Windows.Forms.VisualStyles.CheckBoxState.UncheckedNormal);
                text = new Rectangle(e.Bounds.X + 22, e.Bounds.Y, e.Bounds.Width - 22, e.Bounds.Height);
            }
            TextRenderer.DrawText(e.Graphics, e.SubItem.Text, mods.Font, text, color, TextFormatFlags.VerticalCenter | TextFormatFlags.EndEllipsis | TextFormatFlags.NoPrefix);
        };
        mods.ItemChecked += delegate(object sender, ItemCheckedEventArgs e) { mods.Invalidate(e.Item.Bounds); };
        mods.Resize += delegate { mods.Columns[0].Width = Math.Max(200, mods.ClientSize.Width - mods.Columns[1].Width - 2); };
        mods.ItemChecked += delegate {
            if (!loading) {
                pending = true;
                loading = true; profiles.SelectedIndex = 3; loading = false;
                SetSelectionSummary();
            }
        };
        mods.SelectedIndexChanged += delegate { UpdateDetails(); };
        split.Panel1.Controls.Add(mods);
        TableLayoutPanel info = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 2, BackColor = panel, Padding = new Padding(17, 15, 17, 15) };
        info.RowStyles.Add(new RowStyle(SizeType.Absolute, 27)); info.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        info.Controls.Add(new Label { Text = "Details", AutoSize = true, ForeColor = muted, Font = new Font("Segoe UI Semibold", 9) }, 0, 0);
        detail = new RichTextBox { Dock = DockStyle.Fill, ReadOnly = true, BackColor = panel, ForeColor = ink, BorderStyle = BorderStyle.None, Font = new Font("Segoe UI", 10), DetectUrls = false };
        info.Controls.Add(detail, 0, 1); split.Panel2.Controls.Add(info); root.Controls.Add(split, 0, 2);

        actions = new FlowLayoutPanel { Dock = DockStyle.Fill, WrapContents = false, Padding = new Padding(0, 12, 0, 0) };
        Button launch = Button("Play with mods", async delegate { await Play(); }, 170);
        launch.BackColor = Color.FromArgb(33, 131, 130); launch.FlatAppearance.BorderColor = launch.BackColor; launch.Font = new Font("Segoe UI Semibold", 10);
        actions.Controls.Add(launch);
        actions.Controls.Add(Button("Apply selection", async delegate { await ApplySelection(); }, 140));
        actions.Controls.Add(Button("Restore vanilla", async delegate { await RestoreVanilla(); }, 140));
        moreMenu = new ContextMenuStrip { BackColor = panel, ForeColor = ink, ShowImageMargin = false, Font = Font };
        moreMenu.Items.Add("Import ZIP...", null, async delegate { await ImportMod(); });
        moreMenu.Items.Add("Export selected...", null, async delegate { await ExportMod(); });
        moreMenu.Items.Add(new ToolStripSeparator());
        moreMenu.Items.Add("Open mods folder", null, delegate { OpenFolder(Path.Combine(game, "Mods", "Library")); });
        moreMenu.Items.Add("Open backups", null, delegate { OpenFolder(Path.Combine(game, "Mods", "Manager", "backups")); });
        moreMenu.Items.Add(new ToolStripSeparator());
        moreMenu.Items.Add("Refresh", null, async delegate { await RefreshStatus(false); });
        moreMenu.Items.Add("Verify files", null, async delegate { await RunOperation("verify"); });
        moreMenu.Items.Add("Diagnostics", null, async delegate { await ShowRuntimeDiagnostics(); });
        moreMenu.Items.Add("Modding guide", null, delegate { OpenGuide(); });
        Button more = null;
        more = Button("More \u25BE", delegate { moreMenu.Show(more, new Point(0, more.Height)); }, 96);
        actions.Controls.Add(more);
        root.Controls.Add(actions, 0, 3);
        Panel statusBar = new Panel { Dock = DockStyle.Fill };
        statusLabel = new Label { Text = "Ready", AutoEllipsis = true, Dock = DockStyle.Fill, ForeColor = muted, Font = new Font("Segoe UI", 9) };
        summary = new Label { Text = "", AutoSize = true, Dock = DockStyle.Right, ForeColor = Color.FromArgb(91, 192, 187), Font = new Font("Segoe UI", 9) };
        statusBar.Controls.Add(statusLabel); statusBar.Controls.Add(summary); root.Controls.Add(statusBar, 0, 4);
        progress = new ProgressBar { Dock = DockStyle.Fill, Style = ProgressBarStyle.Marquee, Visible = false };
        root.Controls.Add(progress, 0, 5);
        pages.SelectedIndexChanged += async delegate {
            if (selfTest) return;
            if (pages.SelectedIndex == 1) await liveEditor.InitializeAsync(true);
            if (pages.SelectedIndex == 2) await saveEditor.InitializeAsync(true);
            if (pages.SelectedIndex == 2 && savePages.SelectedIndex == 1) await advancedEditor.InitializeAsync(true);
        };
    }

    private Button Button(string text, EventHandler action, int width)
    {
        Button button = new Button { Text = text, Width = width, Height = 34, FlatStyle = FlatStyle.Flat, BackColor = panel, ForeColor = ink, Margin = new Padding(0, 0, 9, 0), Cursor = Cursors.Hand };
        button.FlatAppearance.BorderColor = Color.FromArgb(54, 72, 90);
        button.Click += action; allButtons.Add(button); return button;
    }

    private static string Quote(string value)
    {
        // All arguments are individual Windows argv entries. Double backslashes
        // before quotes and the closing quote according to CommandLineToArgvW.
        StringBuilder result = new StringBuilder("\"");
        int slashes = 0;
        foreach (char valueChar in value)
        {
            if (valueChar == '\\') { slashes++; continue; }
            if (valueChar == '"') { result.Append('\\', slashes * 2 + 1); result.Append('"'); }
            else { result.Append('\\', slashes); result.Append(valueChar); }
            slashes = 0;
        }
        result.Append('\\', slashes * 2); result.Append('"');
        return result.ToString();
    }

    private Task<Dictionary<string, object>> CallBackend(params string[] args)
    {
        return CallBackendAt(game, args);
    }

    internal static async Task<Dictionary<string, object>> CallBackendAt(string game, params string[] args)
    {
        JavaScriptSerializer json = new JavaScriptSerializer { MaxJsonLength = 16 * 1024 * 1024 };
        string script = Path.Combine(game, "Mods", "Manager", "mod_loader.py");
        string python = Environment.GetEnvironmentVariable("RTW3_PYTHON");
        if (String.IsNullOrWhiteSpace(python)) python = "python.exe";
        return await Task.Run(delegate {
            ProcessStartInfo start = new ProcessStartInfo(python, Quote(script) + " " + String.Join(" ", args.Select(Quote)));
            start.WorkingDirectory = game; start.UseShellExecute = false; start.CreateNoWindow = true;
            start.RedirectStandardOutput = true; start.RedirectStandardError = true;
            start.StandardOutputEncoding = Encoding.UTF8; start.StandardErrorEncoding = Encoding.UTF8;
            using (Process process = Process.Start(start))
            {
                Task<string> output = process.StandardOutput.ReadToEndAsync();
                Task<string> errors = process.StandardError.ReadToEndAsync();
                if (!process.WaitForExit(150000)) throw new Exception("The operation is taking longer than expected. Check for a Steam login window, then refresh.");
                string raw = output.Result.Trim();
                if (String.IsNullOrWhiteSpace(raw)) throw new Exception(errors.Result.Trim().Length > 0 ? errors.Result.Trim() : "Python returned no response. Install Python 3.11 or newer, or set RTW3_PYTHON.");
                Dictionary<string, object> response;
                try { response = json.Deserialize<Dictionary<string, object>>(raw); }
                catch { throw new Exception("Unexpected loader response: " + raw.Substring(0, Math.Min(raw.Length, 600))); }
                if (!response.ContainsKey("ok") || !(bool)response["ok"]) throw new Exception(response.ContainsKey("message") ? response["message"].ToString() : "The loader stopped.");
                return response;
            }
        });
    }

    private void SetBusy(bool value, string message)
    {
        busy = value; progress.Visible = value;
        pages.Enabled = !value;
        foreach (Button button in allButtons) button.Enabled = !value;
        mods.Enabled = !value; profiles.Enabled = !value;
        statusLabel.Text = message;
        UseWaitCursor = value;
    }

    private void ShowFailure(Exception error)
    {
        statusLabel.Text = "Stopped: " + error.Message;
        if (!selfTest) MessageBox.Show(this, error.Message, "RTW3 Mod Manager", MessageBoxButtons.OK, MessageBoxIcon.Information);
    }

    private Form BuildRuntimeDiagnostics(Dictionary<string, object> response)
    {
        StringBuilder text = new StringBuilder();
        text.AppendLine("Framework " + response["framework_api"] + "  |  Session: " + response["session_state"]);
        text.AppendLine("These checks inspect startup patches. They do not measure battle frame rate.");
        text.AppendLine();
        foreach (object warning in (ArrayList)response["warnings"]) text.AppendLine("Notice: " + warning);
        Dictionary<string, object> last = response["last_launch"] as Dictionary<string, object>;
        if (last != null) {
            text.AppendLine();
            text.AppendLine("LAST STARTUP  " + last["started_utc"]);
            text.AppendLine("Result: " + last["state"] + "  |  Host time: " + last["elapsed_ms"] + " ms");
            if (last.ContainsKey("error")) text.AppendLine("Stopped: " + last["error"]);
            foreach (object entry in (ArrayList)last["adapters"]) {
                Dictionary<string, object> item = (Dictionary<string, object>)entry;
                text.AppendLine(String.Format("{0,-25} {1,-10} {2,10} ms", item["adapter"], item["state"], item["elapsed_ms"]));
                if (item.ContainsKey("error")) text.AppendLine("  " + item["error"]);
            }
            text.AppendLine("Recorded patch sites: " + ((ArrayList)last["hooks"]).Count);
        }
        text.AppendLine(); text.AppendLine("CURRENT SELECTION / LOAD ORDER");
        int number = 0;
        foreach (object entry in (ArrayList)response["plan"]) {
            Dictionary<string, object> item = (Dictionary<string, object>)entry;
            text.AppendLine((++number).ToString().PadLeft(2) + ". " + item["adapter"]);
            Dictionary<string, object> settings = (Dictionary<string, object>)item["settings"];
            foreach (KeyValuePair<string, object> setting in settings) text.AppendLine("      " + setting.Key + " = " + setting.Value);
        }
        foreach (object entry in (ArrayList)response["mismatches"]) {
            Dictionary<string, object> item = (Dictionary<string, object>)entry;
            text.AppendLine("Changed patch: " + item["adapter"] + " at " + item["address"]);
        }
        Form dialog = new Form { Text = "RTW3 - Runtime diagnostics", Size = new Size(850, 650), MinimumSize = new Size(620, 400),
            StartPosition = FormStartPosition.CenterParent, BackColor = bg, ForeColor = ink };
        TextBox report = new TextBox { Dock = DockStyle.Fill, ReadOnly = true, BackColor = panel, ForeColor = ink,
            BorderStyle = BorderStyle.None, Font = new Font("Consolas", 10), Text = text.ToString(), Multiline = true,
            ScrollBars = ScrollBars.Vertical, WordWrap = true };
        FlowLayoutPanel controls = new FlowLayoutPanel { Dock = DockStyle.Bottom, Height = 50, Padding = new Padding(8) };
        Button close = new Button { Text = "Close", Width = 100, Height = 30, DialogResult = DialogResult.Cancel };
        Button guide = new Button { Text = "Framework guide", Width = 150, Height = 30 };
        guide.Click += delegate { Process.Start(new ProcessStartInfo(Path.Combine(game, "Mods", "Manager", "FRAMEWORK.md")) { UseShellExecute = true }); };
        controls.Controls.Add(close); controls.Controls.Add(guide);
        dialog.Controls.Add(report); dialog.Controls.Add(controls); dialog.CancelButton = close;
        dialog.ActiveControl = close;
        dialog.Shown += delegate { report.Select(0, 0); close.Focus(); };
        return dialog;
    }

    private async Task ShowRuntimeDiagnostics()
    {
        if (busy) return;
        SetBusy(true, "Checking runtime patches...");
        try {
            Dictionary<string, object> response = await CallBackend("runtime-diagnostics");
            SetBusy(false, "Runtime checks complete. Selection shown is the applied selection.");
            using (Form dialog = BuildRuntimeDiagnostics(response)) dialog.ShowDialog(this);
        }
        catch (Exception error) { ShowFailure(error); }
        finally { SetBusy(false, statusLabel.Text); }
    }

    private async Task RunSelfTest()
    {
        Dictionary<string, object> result = new Dictionary<string, object>();
        try
        {
            if (current == null) throw new Exception(statusLabel.Text);
            if (mods.Items.Count < 2) throw new Exception("Built-in mods were not rendered.");
            if (profiles.SelectedIndex < 0) throw new Exception("No profile was selected.");
            if (String.IsNullOrWhiteSpace(detail.Text)) throw new Exception("Details did not render.");
            Dictionary<string, object> verified = await CallBackend("verify");
            result["ok"] = true;
            result["mods_rendered"] = mods.Items.Count;
            result["profile"] = profiles.SelectedItem.ToString();
            result["details_populated"] = true;
            result["backend_verified"] = verified["ok"];
            Size previousSize = Size; Size = MinimumSize; PerformLayout();
            Button moreButton = allButtons.Single(button => button.Text.StartsWith("More"));
            if (!moreButton.Parent.ClientRectangle.Contains(moreButton.Bounds)) throw new Exception("More button is clipped at minimum window size.");
            if (!moreMenu.Items.Cast<ToolStripItem>().Any(entry => entry.Text == "Diagnostics")) throw new Exception("Diagnostics is missing from the More menu.");
            result["diagnostics_visible_at_minimum_size"] = true;
            Size = previousSize; PerformLayout();
            Dictionary<string, object> diagnostic = await CallBackend("runtime-diagnostics");
            using (Form dialog = BuildRuntimeDiagnostics(diagnostic)) {
                dialog.ShowInTaskbar = false; dialog.Opacity = 0; dialog.Show(this);
                dialog.PerformLayout(); Application.DoEvents();
                if (dialog.Controls.OfType<TextBox>().Single().Text.Length < 100) throw new Exception("Runtime diagnostics text did not populate.");
                using (Bitmap capture = new Bitmap(dialog.Width, dialog.Height)) {
                    dialog.DrawToBitmap(capture, new Rectangle(Point.Empty, dialog.Size));
                    capture.Save(Path.Combine(game, "Mods", "Manager", "runtime-diagnostics-preview.png"), System.Drawing.Imaging.ImageFormat.Png);
                }
                result["runtime_diagnostics_constructed"] = true;
            }
            result["window_constructed"] = true;
            GameToolsHost.RenderPreview(Path.Combine(game, "Mods", "Manager", "in-game-cheats-button-preview.png"));
            result["cheat_menu_constructed"] = liveEditor.Controls.Count > 0;
            result["editor_tabs"] = pages.TabPages.Cast<TabPage>().Select(page => page.Text).ToArray();
            using (Bitmap capture = new Bitmap(Width, Height)) {
                DrawToBitmap(capture, new Rectangle(Point.Empty, Size));
                capture.Save(Path.Combine(game, "Mods", "Manager", "manager-preview.png"), System.Drawing.Imaging.ImageFormat.Png);
            }
            pages.SelectedIndex = 2;
            await saveEditor.InitializeAsync(true);
            if (!saveEditor.HasLoadedSnapshot) throw new Exception("Save editor could not load a saved campaign.");
            result["save_editor_embedded"] = true;
            result["save_editor_loaded_snapshot"] = saveEditor.HasLoadedSnapshot;
            result["editable_fields"] = saveEditor.EditableFieldCount;
            using (Bitmap capture = new Bitmap(Width, Height)) {
                DrawToBitmap(capture, new Rectangle(Point.Empty, Size));
                capture.Save(Path.Combine(game, "Mods", "Manager", "save-editor-preview.png"), System.Drawing.Imaging.ImageFormat.Png);
            }
            savePages.SelectedIndex = 1;
            await advancedEditor.InitializeAsync(true);
            if (advancedEditor.EditableCount < 10) throw new Exception("Advanced fields did not populate.");
            result["advanced_fields_visible"] = advancedEditor.VisibleFieldCount;
            result["advanced_fields_editable_in_general"] = advancedEditor.EditableCount;
            using (Bitmap capture = new Bitmap(Width, Height)) {
                DrawToBitmap(capture, new Rectangle(Point.Empty, Size));
                capture.Save(Path.Combine(game, "Mods", "Manager", "advanced-save-editor-preview.png"), System.Drawing.Imaging.ImageFormat.Png);
            }
            pages.SelectedIndex = 1;
            await liveEditor.InitializeAsync(true);
            result["live_editor_embedded"] = liveEditor.IsLive;
            using (Bitmap capture = new Bitmap(Width, Height)) {
                DrawToBitmap(capture, new Rectangle(Point.Empty, Size));
                capture.Save(Path.Combine(game, "Mods", "Manager", "live-cheats-preview.png"), System.Drawing.Imaging.ImageFormat.Png);
            }
            Dictionary<string, object> savesResult = await CallBackend("cheats-list");
            result["saves_detected"] = ((ArrayList)savesResult["saves"]).Count;
            result["submarine_designer_in_manager"]=false;
            result["interactive_walkthrough"] = false;
        }
        catch (Exception error) { result["ok"] = false; result["message"] = error.ToString(); Environment.ExitCode = 1; }
        File.WriteAllText(Path.Combine(game, "Mods", "Manager", "ui-self-test.json"), json.Serialize(result));
        busy = false; Close();
    }

    private async Task RefreshStatus(bool first)
    {
        if (busy) return;
        SetBusy(true, "Checking mods and game files...");
        try { Render(await CallBackend(first ? "bootstrap" : "status")); }
        catch (Exception error) { ShowFailure(error); }
        finally { SetBusy(false, statusLabel.Text); }
    }

    private void Render(Dictionary<string, object> response)
    {
        if (response.ContainsKey("status")) response = (Dictionary<string, object>)response["status"];
        current = response; loading = true;
        mods.Items.Clear();
        foreach (object obj in (ArrayList)response["mods"])
        {
            Dictionary<string, object> mod = (Dictionary<string, object>)obj;
            bool enabled = (bool)mod["enabled"];
            ListViewItem item = new ListViewItem(mod["name"].ToString());
            item.SubItems.Add(enabled ? (mod.ContainsKey("pending_restart") && (bool)mod["pending_restart"] ? "Next launch" : "Active") : "Off");
            item.Tag = mod; item.Checked = enabled;
            if (mod.ContainsKey("experimental") && (bool)mod["experimental"]) item.ForeColor = Color.FromArgb(240, 189, 112);
            mods.Items.Add(item);
        }
        string[] selected = CheckedIds();
        profiles.SelectedIndex = selected.Length == 0 ? 2 : selected.All(id => id == "campaign-events" || id == "week-display") && selected.Contains("campaign-events") ? 0 : selected.All(id => id == "campaign-events" || id == "weekly-calendar" || id == "week-display") && selected.Contains("weekly-calendar") ? 1 : 3;
        buildLabel.Text = "Steam build " + response["build"] + "\nLocal copy, Steam required";
        pending = false; loading = false;
        if (mods.Items.Count > 0) mods.Items[0].Selected = true;
        bool running = ((ArrayList)response["running"]).Count > 0;
        int invalid = ((ArrayList)response["invalid_mods"]).Count;
        statusLabel.Text = running ? "Game is running. Close RTW3 before changing mods." : invalid > 0 ? invalid + " invalid package(s). Check mod.json and refresh." : "Ready. Select your mods, then Apply or Play.";
        if (response.ContainsKey("runtime_restart_required") && (bool)response["runtime_restart_required"])
            statusLabel.Text = "New runtime mods are selected for next launch. Save and close RTW3, then press Play with mods.";
        SetSelectionSummary(); UpdateDetails();
    }

    private string[] CheckedIds()
    {
        return mods.Items.Cast<ListViewItem>().Where(item => item.Checked).Select(item => ((Dictionary<string, object>)item.Tag)["id"].ToString()).ToArray();
    }

    private void SetSelectionSummary()
    {
        summary.Text = CheckedIds().Length + " selected" + (pending ? "  |  unapplied" : "  |  applied");
    }

    private void ProfileChanged(object sender, EventArgs e)
    {
        if (loading || profiles.SelectedIndex == 3) return;
        loading = true;
        foreach (ListViewItem item in mods.Items)
        {
            string id = ((Dictionary<string, object>)item.Tag)["id"].ToString();
            item.Checked = profiles.SelectedIndex == 0 ? (id == "campaign-events" || id == "week-display") : profiles.SelectedIndex == 1 && (id == "campaign-events" || id == "weekly-calendar" || id == "week-display");
        }
        loading = false; pending = true; SetSelectionSummary();
    }

    private void UpdateDetails()
    {
        if (mods.SelectedItems.Count != 1) { detail.Text = "Select a mod to see its description and affected files."; return; }
        Dictionary<string, object> mod = (Dictionary<string, object>)mods.SelectedItems[0].Tag;
        StringBuilder text = new StringBuilder();
        text.AppendLine(mod["name"].ToString());
        text.AppendLine((mod["kind"].ToString() == "runtime" ? "Runtime mod" : "Game files") + ", version " + mod["version"] +
                        (mod.ContainsKey("experimental") && (bool)mod["experimental"] ? ", experimental (amber in the list)" : ""));
        text.AppendLine();
        text.AppendLine(mod["description"].ToString()); text.AppendLine();
        text.AppendLine("ID: " + mod["id"]);
        ArrayList targets = (ArrayList)mod["targets"];
        if (targets.Count > 0) { text.AppendLine(); text.AppendLine("Files managed:"); foreach (object target in targets) text.AppendLine("  " + target); }
        if (mod["kind"].ToString() == "runtime") { text.AppendLine(); text.AppendLine("Loads after Steam starts the game. The executable file stays unchanged. Closing the game removes the runtime hook."); }
        ArrayList requires = (ArrayList)mod["requires"]; if (requires.Count > 0) text.AppendLine("Requires: " + String.Join(", ", requires.Cast<object>()));
        ArrayList conflicts = (ArrayList)mod["conflicts"]; if (conflicts.Count > 0) text.AppendLine("Conflicts: " + String.Join(", ", conflicts.Cast<object>()));
        detail.Text = text.ToString();
    }

    private bool ConfirmExperimental()
    {
        var selected = mods.Items.Cast<ListViewItem>().Where(item => item.Checked && ((Dictionary<string, object>)item.Tag).ContainsKey("experimental") && (bool)((Dictionary<string, object>)item.Tag)["experimental"]).ToList();
        if (selected.Count == 0) return true;
        StringBuilder warning = new StringBuilder("Experimental mods selected:\n");
        foreach (ListViewItem item in selected)
        {
            Dictionary<string, object> mod = (Dictionary<string, object>)item.Tag;
            warning.AppendLine("- " + mod["name"]);
            if (mod["id"].ToString() == "weekly-calendar")
                warning.AppendLine("Budgets, construction, research, AI and timers still process once per turn. They are NOT balanced for weekly turns.\n");
            if (mod["id"].ToString() == "large-hulls")
                warning.AppendLine("Class limits are expanded. Above 90,000 tons machinery uses an estimate. Full designs and gameplay are not yet validated.\n");
            if (mod["id"].ToString() == "legacy-fleet")
                warning.AppendLine("Manual legacy fleets are available for all start years. Use a separate new-campaign slot.\n");
            if (mod["id"].ToString() == "live-cheats")
                warning.AppendLine("Live edits change the running campaign. Save in RTW3 to keep them, or reload an earlier save to undo them.\n");
            if (mod["id"].ToString() == "timeline-2030")
                warning.AppendLine("End checks extend through 2030 only. New modern research and weapons are NOT included; long-campaign balance is unverified. Keep this mod enabled when continuing a save beyond 1989.\n");
            if (mod["id"].ToString() == "in-game-submarines")
                warning.AppendLine("Adds SS - Submarine class to the original Ship design screen. Native finish saves a submarine blueprint, not a surface ship. Only class label, availability and accuracy affect native boats. Other specs are projections; tactical controls are not implemented. Restart RTW3 to unload/update.\n");
        }
        warning.Append("\nUse a separate test campaign. Start with these mods?");
        return MessageBox.Show(this, warning.ToString(), "Experimental mods", MessageBoxButtons.YesNo, MessageBoxIcon.Warning, MessageBoxDefaultButton.Button2) == DialogResult.Yes;
    }

    private async Task ApplySelection()
    {
        await RunOperation("apply", "--enabled", String.Join(",", CheckedIds()));
    }

    private async Task RestoreVanilla()
    {
        await RunOperation("apply", "--enabled", "");
    }

    private async Task RunOperation(params string[] args)
    {
        if (busy) return;
        SetBusy(true, "Working... backups and verification are automatic.");
        try
        {
            Dictionary<string, object> result = await CallBackend(args);
            string message = result.ContainsKey("message") ? result["message"].ToString() : "Done.";
            if (result.ContainsKey("status")) Render(result); else Render(await CallBackend("status"));
            statusLabel.Text = message;
        }
        catch (Exception error) { ShowFailure(error); }
        finally { SetBusy(false, statusLabel.Text); }
    }

    private async Task Play()
    {
        if (busy || liveEditor.IsBusy || saveEditor.IsBusy || advancedEditor.IsBusy || !ConfirmExperimental()) return;
        string selected = String.Join(",", CheckedIds());
        SetBusy(true, "Applying mods, then starting the game through Steam...");
        try
        {
            await CallBackend("apply", "--enabled", selected);
            Dictionary<string, object> result = await CallBackend("launch", "--accept-experimental");
            Render(result); statusLabel.Text = result["message"].ToString();
        }
        catch (Exception error) { ShowFailure(error); }
        finally { SetBusy(false, statusLabel.Text); }
    }

    private async Task ImportMod()
    {
        using (OpenFileDialog picker = new OpenFileDialog { Filter = "RTW3 mod package (*.zip)|*.zip", Title = "Import mod ZIP" })
        { if (picker.ShowDialog(this) == DialogResult.OK) await RunOperation("import", "--zip", picker.FileName); }
    }

    private async Task ExportMod()
    {
        if (mods.SelectedItems.Count != 1) { MessageBox.Show(this, "Select a mod first."); return; }
        Dictionary<string, object> mod = (Dictionary<string, object>)mods.SelectedItems[0].Tag;
        using (SaveFileDialog picker = new SaveFileDialog { Filter = "RTW3 mod package (*.zip)|*.zip", FileName = mod["id"] + "-" + mod["version"] + ".zip", OverwritePrompt = false, Title = "Export mod package" })
        { if (picker.ShowDialog(this) == DialogResult.OK) await RunOperation("export", "--mod", mod["id"].ToString(), "--zip", picker.FileName); }
    }

    private void OpenFolder(string folder)
    {
        Directory.CreateDirectory(folder);
        Process.Start(new ProcessStartInfo(folder) { UseShellExecute = true });
    }

    private void OpenGuide()
    {
        Process.Start(new ProcessStartInfo(Path.Combine(game, "Mods", "Manager", "MODDING.md")) { UseShellExecute = true });
    }
}
