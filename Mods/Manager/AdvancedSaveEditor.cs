using System;
using System.Collections;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

internal sealed class AdvancedSaveEditor : UserControl
{
    private sealed class Choice { internal string Id, Label; public override string ToString() { return Label; } }
    private readonly Func<string[], Task<Dictionary<string, object>>> backend;
    private readonly bool quiet;
    private readonly JavaScriptSerializer json = new JavaScriptSerializer();
    private readonly Dictionary<string, Dictionary<string, object>> pending = new Dictionary<string, Dictionary<string, object>>();
    private ComboBox saves, sections;
    private TextBox search;
    private DataGridView grid;
    private Label status, pageInfo;
    private Button apply, previous, next;
    private TableLayoutPanel root;
    private bool loading, initialized, running;
    private int offset, total;
    private string hash, boundPath;
    internal bool IsBusy { get; private set; }
    internal int VisibleFieldCount { get { return grid.Rows.Count; } }
    internal int EditableCount { get; private set; }

    internal AdvancedSaveEditor(Func<string[], Task<Dictionary<string, object>>> callback, bool suppressDialogs)
    {
        backend = callback; quiet = suppressDialogs; Dock = DockStyle.Fill;
        BackColor = Color.FromArgb(18, 26, 35); ForeColor = Color.FromArgb(229, 236, 243); Font = new Font("Segoe UI", 10);
        root = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(18), ColumnCount = 1, RowCount = 5 };
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 64)); root.RowStyles.Add(new RowStyle(SizeType.Absolute, 38));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 42)); root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 104)); Controls.Add(root);
        root.Controls.Add(new Label { Text = "ADVANCED SAVED-CAMPAIGN FIELDS\nCampaign date/settings, nation economy/training/research progress, ship names, repairs and construction.\nIDs, counts, design links and unsupported fields are read-only. Close RTW3 before applying.", Dock = DockStyle.Fill }, 0, 0);
        saves = new ComboBox { Dock = DockStyle.Fill, DropDownStyle = ComboBoxStyle.DropDownList };
        root.Controls.Add(saves, 0, 1);
        FlowLayoutPanel filters = new FlowLayoutPanel { Dock = DockStyle.Fill, WrapContents = false };
        sections = new ComboBox { Width = 215, DropDownStyle = ComboBoxStyle.DropDownList };
        search = new TextBox { Width = 190 };
        search.AccessibleName = "Search field names or values";
        ToolTip hints = new ToolTip(); hints.SetToolTip(search, "Search field names or current values, for example ResearchPoints or Ship0RepairTime.");
        Disposed += delegate { hints.Dispose(); };
        Button find = MakeButton("Search", 82), reload = MakeButton("Reload / discard edits", 190);
        previous = MakeButton("Previous", 90); next = MakeButton("Next", 70);
        filters.Controls.AddRange(new Control[] { sections, search, find, previous, next });
        pageInfo = new Label { AutoSize = true, Margin = new Padding(7, 6, 0, 0) }; filters.Controls.Add(pageInfo);
        root.Controls.Add(filters, 0, 2);
        grid = new DataGridView { Dock = DockStyle.Fill, BackgroundColor = BackColor, BorderStyle = BorderStyle.None,
                                  AllowUserToAddRows = false, AllowUserToDeleteRows = false, RowHeadersVisible = false,
                                  AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill, MultiSelect = false,
                                  SelectionMode = DataGridViewSelectionMode.CellSelect, EnableHeadersVisualStyles = false };
        grid.DefaultCellStyle.BackColor = Color.FromArgb(27, 38, 50); grid.DefaultCellStyle.ForeColor = ForeColor;
        grid.DefaultCellStyle.SelectionBackColor = Color.FromArgb(33, 105, 110);
        grid.DefaultCellStyle.SelectionForeColor = Color.White; grid.DefaultCellStyle.Font = Font;
        grid.ColumnHeadersDefaultCellStyle.BackColor = Color.FromArgb(35, 50, 64); grid.ColumnHeadersDefaultCellStyle.ForeColor = ForeColor;
        foreach (string title in new[] { "Section", "Field", "Current value", "New value", "Access" }) grid.Columns.Add(title, title);
        grid.Columns[0].FillWeight = 95; grid.Columns[1].FillWeight = 155; grid.Columns[2].FillWeight = 100; grid.Columns[3].FillWeight = 100; grid.Columns[4].FillWeight = 70;
        foreach (DataGridViewColumn column in grid.Columns) { column.SortMode = DataGridViewColumnSortMode.NotSortable; column.ReadOnly = column.Index != 3; }
        root.Controls.Add(grid, 0, 3);
        Panel bottom = new Panel { Dock = DockStyle.Fill };
        FlowLayoutPanel buttons = new FlowLayoutPanel { Dock = DockStyle.Top, Height = 43, Padding = new Padding(0, 8, 0, 0) };
        apply = MakeButton("Back up and apply edits", 205); apply.BackColor = Color.FromArgb(33, 131, 130);
        buttons.Controls.Add(apply); buttons.Controls.Add(reload);
        status = new Label { Dock = DockStyle.Fill, AutoEllipsis = true, ForeColor = Color.FromArgb(155, 174, 191), Padding = new Padding(0, 4, 0, 0) };
        bottom.Controls.Add(status); bottom.Controls.Add(buttons); root.Controls.Add(bottom, 0, 4);
        saves.SelectedIndexChanged += async delegate {
            if (loading || IsBusy) return;
            if (pending.Count > 0 && !ConfirmDiscard()) {
                loading = true;
                for (int i = 0; i < saves.Items.Count; i++) if (((Choice)saves.Items[i]).Id == boundPath) saves.SelectedIndex = i;
                loading = false; return;
            }
            pending.Clear(); hash = null; offset = 0;
            await LoadFields(true);
        };
        sections.SelectedIndexChanged += async delegate { if (!loading && !IsBusy) { offset = 0; await LoadFields(false); } };
        find.Click += async delegate { offset = 0; await LoadFields(false); };
        search.KeyDown += async delegate(object sender, KeyEventArgs e) { if (e.KeyCode == Keys.Enter) { e.SuppressKeyPress = true; offset = 0; await LoadFields(false); } };
        previous.Click += async delegate { offset = Math.Max(0, offset-250); await LoadFields(false); };
        next.Click += async delegate { offset += 250; await LoadFields(false); };
        reload.Click += async delegate { if (ConfirmDiscard()) { pending.Clear(); hash = null; await LoadFields(false); } };
        apply.Click += async delegate { await ApplyEdits(); };
        grid.CellEndEdit += delegate(object sender, DataGridViewCellEventArgs e) {
            if (loading || e.RowIndex < 0 || e.ColumnIndex != 3) return;
            DataGridViewRow row = grid.Rows[e.RowIndex]; Dictionary<string, object> spec = (Dictionary<string, object>)row.Tag;
            string key = spec["section"]+"\u001f"+spec["key"], value = Convert.ToString(row.Cells[3].Value);
            if (value == spec["value"].ToString()) pending.Remove(key);
            else pending[key] = new Dictionary<string, object> { { "section", spec["section"] }, { "key", spec["key"] }, { "expected", spec["value"] }, { "value", value } };
            UpdateSummary();
        };
        grid.SelectionChanged += delegate {
            if (!loading && grid.CurrentRow != null) {
                var spec = grid.CurrentRow.Tag as Dictionary<string, object>;
                if (spec != null) status.Text = pending.Count+" pending edit(s). "+spec["note"];
            }
        };
        UpdateSummary();
    }

    private Button MakeButton(string text, int width)
    {
        return new Button { Text = text, Width = width, Height = 30, FlatStyle = FlatStyle.Flat,
                            BackColor = Color.FromArgb(27, 38, 50), ForeColor = ForeColor, Margin = new Padding(0, 0, 7, 0) };
    }

    private bool ConfirmDiscard()
    {
        return pending.Count == 0 || quiet || MessageBox.Show(FindForm(), "Discard the pending field edits?", "Save editor", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes;
    }

    internal async Task InitializeAsync(bool force)
    {
        if (IsBusy || (initialized && !force)) return;
        if (initialized) { await LoadFields(false); return; }
        IsBusy = true; root.Enabled = false;
        try {
            Dictionary<string, object> data = await backend(new[] { "cheats-list" });
            loading = true;
            foreach (object obj in (ArrayList)data["saves"]) { var row = (Dictionary<string, object>)obj; saves.Items.Add(new Choice { Id = row["path"].ToString(), Label = row["name"].ToString() }); }
            if (saves.Items.Count > 0) saves.SelectedIndex = 0;
            loading = false; initialized = true;
        }
        catch (Exception error) { status.Text = error.Message; }
        finally { loading = false; IsBusy = false; root.Enabled = true; }
        await LoadFields(true);
    }

    private async Task LoadFields(bool resetSection)
    {
        if (IsBusy || saves.SelectedItem == null) return;
        IsBusy = true; root.Enabled = false;
        try {
            Choice source = (Choice)saves.SelectedItem;
            string section = resetSection || sections.SelectedItem == null ? "General" : sections.SelectedItem.ToString();
            if (section == "All sections") section = "*";
            Dictionary<string, object> data = await backend(new[] { "advanced-inspect", "--save", source.Id, "--section", section, "--query", search.Text, "--offset", offset.ToString() });
            string nextHash = data["sha256"].ToString();
            if (pending.Count > 0 && hash != null && hash != nextHash) throw new Exception("The save changed externally. Use Reload / discard edits before continuing.");
            hash = nextHash; boundPath = source.Id; running = (bool)data["game_running"];
            loading = true;
            if (resetSection) {
                sections.Items.Clear(); sections.Items.Add("All sections");
                foreach (object name in (ArrayList)data["sections"]) sections.Items.Add(name.ToString());
                sections.SelectedItem = "General";
            }
            grid.Rows.Clear(); total = Convert.ToInt32(data["total"]); EditableCount = Convert.ToInt32(data["editable"]);
            foreach (object obj in (ArrayList)data["fields"]) {
                var spec = (Dictionary<string, object>)obj;
                string key = spec["section"]+"\u001f"+spec["key"];
                string value = pending.ContainsKey(key) ? pending[key]["value"].ToString() : spec["value"].ToString();
                int idx = grid.Rows.Add(spec["section"], spec["key"], spec["value"], value, (bool)spec["editable"] ? "Editable" : "Read-only");
                grid.Rows[idx].Tag = spec; grid.Rows[idx].Cells[3].ReadOnly = !(bool)spec["editable"];
                grid.Rows[idx].Cells[3].ToolTipText = spec["note"].ToString();
                if (!(bool)spec["editable"]) grid.Rows[idx].DefaultCellStyle.ForeColor = Color.FromArgb(125, 144, 160);
            }
            previous.Enabled = offset > 0; next.Enabled = offset+250 < total;
            pageInfo.Text = (total == 0 ? "0" : (offset+1)+"-"+Math.Min(offset+250, total))+" / "+total;
            loading = false; UpdateSummary();
        }
        catch (Exception error) { status.Text = error.Message; apply.Enabled = false; }
        finally { loading = false; IsBusy = false; root.Enabled = true; }
    }

    private void UpdateSummary()
    {
        apply.Enabled = pending.Count > 0 && !running && hash != null;
        status.Text = pending.Count+" pending edit(s). "+EditableCount+" editable field(s) in these results. "+(running ? "RTW3 is running: close it and reload fields before applying." : "Each apply backs up the full save slot. Structural and design-linked fields stay protected.");
    }

    private async Task ApplyEdits()
    {
        grid.EndEdit();
        if (IsBusy || pending.Count == 0 || boundPath == null || hash == null) return;
        IsBusy = true; root.Enabled = false;
        try {
            Dictionary<string, object> result = await backend(new[] { "advanced-edit", "--save", boundPath, "--sha", hash, "--changes", json.Serialize(pending.Values.ToArray()) });
            pending.Clear(); hash = null; IsBusy = false;
            await LoadFields(false);
            status.Text = result["message"]+ (result.ContainsKey("backup") ? "\nBackup: "+result["backup"] : "");
        }
        catch (Exception error) { status.Text = error.Message; }
        finally { IsBusy = false; root.Enabled = true; }
    }
}
