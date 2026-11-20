using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

internal sealed partial class CampaignEditorPanel : UserControl
{
    private sealed class Choice
    {
        internal string Id; internal string Label; internal string Kind;
        public override string ToString() { return Label; }
    }
    private readonly Func<string[], Task<Dictionary<string, object>>> backend;
    private readonly Dictionary<string, NumericUpDown> fields = new Dictionary<string, NumericUpDown>();
    private readonly JavaScriptSerializer json = new JavaScriptSerializer();
    private ComboBox saves, nations, ships;
    private NumericUpDown buildTurns;
    private CheckBox editShip, revealEnemy, forceDaytime, clearWeather;
    private Label note, shipCaption;
    private Button apply, refresh, fastBuild, fastRefit, fastBuildAll, fastRefitAll, researchAll, fastAircraft, refillAmmo, decisionsButton;
    private ProgressBar technologyBar;
    private Label technologyText;
    private ComboBox technologyBranches;
    private bool bulkAvailable;
    private bool loading;
    private string hash;
    private readonly bool live;
    private readonly bool quiet;
    private bool initialized;
    private bool gameRunning;
    internal bool IsBusy { get; private set; }
    internal bool IsLive { get { return live; } }
    internal bool HasLoadedSnapshot { get { return hash != null; } }
    internal int SaveCount { get { return saves.Items.Count; } }
    internal int EditableFieldCount { get { return fields.Count; } }
    internal bool CanApply { get { return apply.Enabled && hash != null; } }

    internal CampaignEditorPanel(Func<string[], Task<Dictionary<string, object>>> callback, bool liveMode, bool suppressDialogs)
    {
        backend = callback;
        live = liveMode; quiet = suppressDialogs;
        Dock = DockStyle.Fill; AutoScroll = true;
        BackColor = Color.FromArgb(18, 26, 35); ForeColor = Color.FromArgb(229, 236, 243);
        Font = new Font("Segoe UI", 10);
        TableLayoutPanel root = new TableLayoutPanel { Dock = DockStyle.Top, Height = live ? 1120 : 806, Padding = new Padding(22), ColumnCount = 2, RowCount = 19 };
        root.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 48)); root.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 52));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 90));
        for (int i = 1; i < 18; i++) root.RowStyles.Add(new RowStyle(SizeType.Absolute, i == 8 ? (live ? 120 : 0) : i == 14 ? (live ? 157 : 0) : i == 11 ? (live ? 37 : 0) : (i == 15 || i == 16) ? 44 : i == 17 ? 50 : 37));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        Controls.Add(root);
        Label intro = new Label { Text = live ? "LIVE CAMPAIGN CHEATS  /  F10 IN GAME\nLoad a campaign, refresh, then apply changes while playing.\nThe game updates immediately. Save in RTW3 if you want to keep the changes." : "SAVED CAMPAIGN EDITOR\nSave your campaign and close RTW3 before applying changes here.\nEvery edit backs up the whole slot. Reload the edited save afterward.", Dock = DockStyle.Fill, ForeColor = ForeColor, AutoSize = false };
        root.Controls.Add(intro, 0, 0); root.SetColumnSpan(intro, 2);
        saves = Picker(); AddRow(root, 1, live ? "Running game" : "Saved campaign", saves);
        nations = Picker(); AddRow(root, 2, "Nation", nations);
        AddNumber(root, 3, "Funds", "funds", 0, 1000000000, 10000);
        AddNumber(root, 4, "Naval income level (native budget)", "income_level", 3, 500, 1);
        AddNumber(root, 5, "National income resource base", "income_resources", 1, 10000000, 1000);
        AddNumber(root, 6, "Shipyard / max hull size (tons)", "dock_tons", 1000, 1000000, 1000);
        AddNumber(root, 7, "Research speed % (100 = normal)", "research_speed", 1, 1000, 25);
        AddNumber(root, 9, "Prestige", "prestige", 1, 100, 1);
        AddNumber(root, 10, "Unrest", "unrest", 0, 10, 1);
        if (live) AddNumber(root, 11, "Counterintelligence budget % (0-10)", "counterintelligence_percent", 0, 10, 1);
        FlowLayoutPanel researchBox = new FlowLayoutPanel { Dock = DockStyle.Fill, Visible = live, FlowDirection = FlowDirection.TopDown, WrapContents = false };
        FlowLayoutPanel researchHeader = new FlowLayoutPanel { Width = 650, Height = 25 };
        technologyBar = new ProgressBar { Width = 210, Height = 18 };
        technologyText = new Label { Text = "Technology progress - refresh campaign", AutoSize = true };
        researchHeader.Controls.Add(technologyBar); researchHeader.Controls.Add(technologyText);
        technologyBranches = Picker(); technologyBranches.Dock = DockStyle.None; technologyBranches.Width = 640;
        researchAll = new Button { Text = "Research ALL technologies", Width = 220, Height = 33, Enabled = false };
        fastAircraft = new Button { Text = "Fast aircraft requests (1 turn)", Width = 240, Height = 33, Enabled = false };
        FlowLayoutPanel researchActions = new FlowLayoutPanel { Width = 650, Height = 40 };
        foreach (Button button in new[] { researchAll, fastAircraft }) { button.FlatStyle = FlatStyle.Flat; button.BackColor = Color.FromArgb(27, 38, 50); button.ForeColor = ForeColor; researchActions.Controls.Add(button); }
        researchBox.Controls.Add(researchHeader); researchBox.Controls.Add(technologyBranches); researchBox.Controls.Add(researchActions);
        root.Controls.Add(researchBox, 0, 8); root.SetColumnSpan(researchBox, 2);
        ships = Picker(); ships.MaxDropDownItems = 20;
        ships.AutoCompleteSource = AutoCompleteSource.ListItems; ships.AutoCompleteMode = AutoCompleteMode.SuggestAppend;
        shipCaption = new Label { Text = "Player ships / yard projects", AutoSize = true, Margin = new Padding(0, 5, 0, 0) };
        root.Controls.Add(shipCaption, 0, 12); root.Controls.Add(ships, 1, 12);
        FlowLayoutPanel shipBar = new FlowLayoutPanel { Dock = DockStyle.Fill };
        editShip = new CheckBox { Text = "Set remaining build turns", AutoSize = true, Margin = new Padding(0, 5, 8, 0) };
        buildTurns = new NumericUpDown { Minimum = 1, Maximum = 1200, Value = 1, Width = 80, ThousandsSeparator = true };
        shipBar.Controls.Add(editShip); shipBar.Controls.Add(buildTurns);
        root.Controls.Add(shipBar, 0, 13); root.SetColumnSpan(shipBar, 2);
        revealEnemy = new CheckBox { Text = "Reveal all enemy ships (battle-map markers)", AutoSize = true, Enabled = false, Visible = live, Margin = new Padding(0, 5, 0, 0) };
        forceDaytime = new CheckBox { Text = "Force daytime (battle clock keeps running)", AutoSize = true, Enabled = false, Visible = live, Margin = new Padding(0, 5, 0, 0) };
        clearWeather = new CheckBox { Text = "Clear weather / calm seas (both sides)", AutoSize = true, Enabled = false, Visible = live, Margin = new Padding(0, 5, 0, 0) };
        FlowLayoutPanel battleOptions = new FlowLayoutPanel { Dock = DockStyle.Fill, Visible = live, FlowDirection = FlowDirection.TopDown, WrapContents = false };
        battleOptions.Controls.Add(revealEnemy); battleOptions.Controls.Add(forceDaytime); battleOptions.Controls.Add(clearWeather);
        refillAmmo = new Button { Text = "Refill ship ammo ALL", Width = 300, Height = 33, Enabled = false, Visible = live, FlatStyle = FlatStyle.Flat, BackColor = Color.FromArgb(27, 38, 50), ForeColor = ForeColor };
        battleOptions.Controls.Add(refillAmmo);
        battleOptions.Controls.Add(new Label { Text = "Guns + loaded tubes; reserves, aircraft stores and mines stay unchanged.", AutoSize = true, Font = new Font("Segoe UI", 9), ForeColor = Color.FromArgb(155, 174, 191) });
        root.Controls.Add(battleOptions, 0, 14); root.SetColumnSpan(battleOptions, 2);
        FlowLayoutPanel fastButtons = new FlowLayoutPanel { Dock = DockStyle.Fill };
        fastBuild = new Button { Text = "Fast build (1 turn)", Width = 175, Height = 33, Enabled = false };
        fastRefit = new Button { Text = "Fast refit (1 turn)", Width = 175, Height = 33, Enabled = false };
        foreach (Button button in new[] { fastBuild, fastRefit }) { button.FlatStyle = FlatStyle.Flat; button.BackColor = Color.FromArgb(27, 38, 50); button.ForeColor = ForeColor; fastButtons.Controls.Add(button); }
        root.Controls.Add(fastButtons, 0, 15); root.SetColumnSpan(fastButtons, 2);
        FlowLayoutPanel allButtons = new FlowLayoutPanel { Dock = DockStyle.Fill };
        fastBuildAll = new Button { Text = "Fast build ALL (1 turn)", Width = 210, Height = 33, Enabled = false };
        fastRefitAll = new Button { Text = "Fast refit ALL (1 turn)", Width = 210, Height = 33, Enabled = false };
        foreach (Button button in new[] { fastBuildAll, fastRefitAll }) { button.FlatStyle = FlatStyle.Flat; button.BackColor = Color.FromArgb(27, 38, 50); button.ForeColor = ForeColor; allButtons.Controls.Add(button); }
        root.Controls.Add(allButtons, 0, 16); root.SetColumnSpan(allButtons, 2);
        FlowLayoutPanel buttons = new FlowLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(0, 7, 0, 0) };
        apply = new Button { Text = live ? "Apply live changes" : "Back up and apply", Width = 165, Height = 33, Enabled = false };
        refresh = new Button { Text = live ? "Refresh live game" : "Refresh saves", Width = 150, Height = 33 };
        Button addFunds = new Button { Text = "+100,000 funds", Width = 145, Height = 33 };
        decisionsButton = new Button { Text = "Campaign decisions", Width = 180, Height = 33, Visible = live };
        foreach (Button button in new[] { apply, refresh, addFunds, decisionsButton }) { button.FlatStyle = FlatStyle.Flat; button.BackColor = Color.FromArgb(27, 38, 50); button.ForeColor = ForeColor; buttons.Controls.Add(button); }
        apply.BackColor = Color.FromArgb(33, 131, 130);
        root.Controls.Add(buttons, 0, 17); root.SetColumnSpan(buttons, 2);
        note = new Label { Dock = DockStyle.Fill, ForeColor = Color.FromArgb(155, 174, 191), Text = "Income uses the game's native budget level and resource base.\nChanging build turns changes per-turn construction spending, preserving the ship's total cost.", AutoEllipsis = true };
        root.Controls.Add(note, 0, 18); root.SetColumnSpan(note, 2);
        refresh.Click += async delegate { await RefreshSaves(); };
        saves.SelectedIndexChanged += async delegate { if (!loading) await ReadSave(true); };
        nations.SelectedIndexChanged += async delegate { if (!loading) await ReadSave(false); };
        ships.SelectedIndexChanged += delegate {
            Choice ship = ships.SelectedItem as Choice;
            editShip.Checked = false;
            buildTurns.Maximum = ship != null && ship.Kind == "refit" ? 99 : 1200;
            if (ship != null) buildTurns.Value = Math.Max(1, Math.Min(buildTurns.Maximum, Convert.ToInt32(ship.Id.Split(':')[1])));
            UpdateProjectControls();
        };
        fastBuild.Click += delegate { StageFastProject(); };
        fastRefit.Click += delegate { StageFastProject(); };
        fastBuildAll.Click += async delegate { await ApplyAllProjects("build"); };
        fastRefitAll.Click += async delegate { await ApplyAllProjects("refit"); };
        researchAll.Click += async delegate { await ApplyAllProjects("research-all"); };
        fastAircraft.Click += async delegate { await ApplyAllProjects("fast-aircraft"); };
        refillAmmo.Click += async delegate { await ApplyAllProjects("refill-ammo"); };
        addFunds.Click += delegate { fields["funds"].Value = Math.Min(fields["funds"].Maximum, fields["funds"].Value + 100000); };
        decisionsButton.Click += delegate { OpenDecisions(); };
        apply.Click += async delegate { await Apply(); };
        UpdateProjectControls();
    }

    private void UpdateProjectControls()
    {
        Choice ship = ships.SelectedItem as Choice;
        bool enabled = ship != null && (ship.Kind == "build" || ship.Kind == "refit" || ship.Kind == "rebuild") && hash != null && !IsBusy && (live || !gameRunning);
        editShip.Text = ship != null && ship.Kind == "refit" ? "Set refit / repair turns" : "Set remaining build / rebuild turns";
        ships.Enabled = ships.Items.Count > 0 && hash != null && !IsBusy;
        editShip.Enabled = enabled; buildTurns.Enabled = enabled;
        fastBuild.Enabled = enabled && ship.Kind == "build";
        fastRefit.Enabled = enabled && (ship.Kind == "refit" || ship.Kind == "rebuild");
        bool allEnabled = hash != null && !IsBusy && bulkAvailable && (live || !gameRunning);
        fastBuildAll.Enabled = allEnabled && ships.Items.Cast<Choice>().Any(item => item.Kind == "build");
        fastRefitAll.Enabled = allEnabled && ships.Items.Cast<Choice>().Any(item => item.Kind == "refit" || item.Kind == "rebuild");
        researchAll.Enabled = live && allEnabled && researchAll.Tag != null;
        fastAircraft.Enabled = live && allEnabled && fastAircraft.Tag != null;
        revealEnemy.Enabled = live && hash != null && !IsBusy && revealEnemy.Tag != null;
        forceDaytime.Enabled = live && hash != null && !IsBusy && forceDaytime.Tag != null;
        clearWeather.Enabled = live && hash != null && !IsBusy && clearWeather.Tag != null;
        refillAmmo.Enabled = live && allEnabled && refillAmmo.Tag != null;
    }

    private void OpenDecisions()
    {
        Choice save = saves.SelectedItem as Choice;
        if (!live || save == null || hash == null) {
            if (!quiet) MessageBox.Show(FindForm(), "Load a campaign and refresh live cheats before opening decisions.", "Campaign decisions", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return;
        }
        Choice nation = nations.SelectedItem as Choice;
        string profile = nation == null ? "My campaign" : "Campaign " + nation.Label;
        Form window = new Form { Text = "Custom Campaign Decisions", Size = new Size(680, 540), MinimumSize = new Size(600, 460),
                                 StartPosition = FormStartPosition.CenterParent, BackColor = BackColor, ForeColor = ForeColor };
        window.Controls.Add(new DecisionEditorPanel(backend, Convert.ToInt32(save.Id), profile));
        window.Show(FindForm());
    }

    private void StageFastProject()
    {
        Choice ship = ships.SelectedItem as Choice;
        if (ship == null || (!fastBuild.Enabled && !fastRefit.Enabled)) return;
        buildTurns.Value = 1; editShip.Checked = true;
        note.Text = "Staged 1 remaining turn for " + ship.Label + ". Press " + apply.Text + " to apply.\n" +
            (ship.Kind == "refit" ? "The native refit / repair timer changes only for this ship; its maintenance-due counter is preserved." :
             "Remaining construction cost is charged faster, not removed. Ensure sufficient funds; native delays and yard rules still apply.");
    }

    private async Task ApplyAllProjects(string kind)
    {
        bool quick = kind == "research-all" || kind == "fast-aircraft" || kind == "refill-ammo";
        if (kind == "build" ? !fastBuildAll.Enabled : kind == "refit" ? !fastRefitAll.Enabled : kind == "research-all" ? !researchAll.Enabled : kind == "refill-ammo" ? !refillAmmo.Enabled : !fastAircraft.Enabled) return;
        Choice save = saves.SelectedItem as Choice, nation = nations.SelectedItem as Choice;
        if (save == null || nation == null || IsBusy) return;
        // These buttons commit only their own action, never unrelated pending
        // money, budget, reveal or selected-ship edits. Preserve staged scalars.
        Dictionary<string, decimal> pending = fields.Where(pair => pair.Value.Enabled && pair.Value.Tag != null && pair.Value.Value != (decimal)pair.Value.Tag).ToDictionary(pair => pair.Key, pair => pair.Value.Value);
        bool? pendingReveal = revealEnemy.Enabled && (revealEnemy.Checked ? 1 : 0) != (int)revealEnemy.Tag ? (bool?)revealEnemy.Checked : null;
        bool? pendingDaytime = forceDaytime.Enabled && (forceDaytime.Checked ? 1 : 0) != (int)forceDaytime.Tag ? (bool?)forceDaytime.Checked : null;
        bool? pendingWeather = clearWeather.Enabled && (clearWeather.Checked ? 1 : 0) != (int)clearWeather.Tag ? (bool?)clearWeather.Checked : null;
        IsBusy = true; apply.Enabled = false; refresh.Enabled = false; saves.Enabled = false; nations.Enabled = false;
        UpdateProjectControls();
        try {
            Dictionary<string, object> current = await backend(live ? new[] { "live-inspect", "--pid", save.Id } : new[] { "cheats-inspect", "--save", save.Id, "--nation", nation.Id });
            int eligible = quick ? 1 : ((ArrayList)current["ships"]).Cast<Dictionary<string, object>>().Count(ship => kind == "build" ? ship["kind"].ToString() == "build" : ship["kind"].ToString() == "refit" || ship["kind"].ToString() == "rebuild");
            if (eligible == 0) {
                Populate(current, false);
                note.Text = "No eligible " + (kind == "build" ? "new builds" : "refit / repair / rebuild projects") + " for this nation. Ships without active yard jobs are still listed.";
            } else {
                string[] command = live ? new[] { "live-edit", "--pid", save.Id, "--sha", current["sha256"].ToString(), "--values", "{}", "--all-projects", kind } :
                    new[] { "cheats-edit", "--save", save.Id, "--nation", nation.Id, "--sha", current["sha256"].ToString(), "--values", "{}", "--all-projects", kind };
                if (quick) command[command.Length-2] = "--action";
                Dictionary<string, object> result = await backend(command);
                Populate((Dictionary<string, object>)result["save"], false);
                note.Text = result["message"] + (result.ContainsKey("backup") ? "\nBackup: " + result["backup"] : "") + "\nAction applied; no separate Apply click is needed. Other pending edits were not applied.";
            }
        }
        catch (Exception error) { Error(error); }
        finally {
            foreach (KeyValuePair<string, decimal> item in pending) if (fields[item.Key].Enabled) fields[item.Key].Value = Math.Max(fields[item.Key].Minimum, Math.Min(fields[item.Key].Maximum, item.Value));
            if (pendingReveal.HasValue && revealEnemy.Tag != null) revealEnemy.Checked = pendingReveal.Value;
            if (pendingDaytime.HasValue && forceDaytime.Tag != null) forceDaytime.Checked = pendingDaytime.Value;
            if (pendingWeather.HasValue && clearWeather.Tag != null) clearWeather.Checked = pendingWeather.Value;
            IsBusy = false; apply.Enabled = hash != null && (live || !gameRunning); refresh.Enabled = true; saves.Enabled = true; nations.Enabled = true; UpdateProjectControls();
        }
    }

    internal async Task InitializeAsync(bool force)
    {
        if (IsBusy || (initialized && !force)) return;
        initialized = true;
        await RefreshSaves();
    }

    private ComboBox Picker()
    {
        return new ComboBox { Dock = DockStyle.Fill, DropDownStyle = ComboBoxStyle.DropDownList, BackColor = Color.FromArgb(27, 38, 50), ForeColor = ForeColor, FlatStyle = FlatStyle.Flat };
    }

    private void AddRow(TableLayoutPanel root, int row, string caption, Control value)
    {
        root.Controls.Add(new Label { Text = caption, AutoSize = true, Margin = new Padding(0, 5, 0, 0) }, 0, row);
        root.Controls.Add(value, 1, row);
    }

    private void AddNumber(TableLayoutPanel root, int row, string caption, string key, int min, int max, int increment)
    {
        NumericUpDown input = new NumericUpDown { Minimum = min, Maximum = max, Value = min, Increment = increment, Dock = DockStyle.Fill, ThousandsSeparator = true, BackColor = Color.FromArgb(27, 38, 50), ForeColor = ForeColor };
        fields[key] = input; AddRow(root, row, caption, input);
    }

    private void Error(Exception error)
    {
        note.Text = error.Message;
        if (!quiet && !live) MessageBox.Show(FindForm(), error.Message, "Campaign Save Editor", MessageBoxButtons.OK, MessageBoxIcon.Information);
    }

    private async Task RefreshSaves()
    {
        if (IsBusy) return;
        IsBusy = true; refresh.Enabled = false; hash = null; apply.Enabled = false;
        UpdateProjectControls();
        try
        {
            Dictionary<string, object> response = await backend(new[] { live ? "live-list" : "cheats-list" });
            loading = true; saves.Items.Clear();
            foreach (object item in (ArrayList)response["saves"]) { Dictionary<string, object> row = (Dictionary<string, object>)item; saves.Items.Add(new Choice { Id = row["path"].ToString(), Label = row["name"].ToString() }); }
            if (saves.Items.Count > 0) saves.SelectedIndex = 0;
            loading = false;
            IsBusy = false;
            if (saves.Items.Count > 0) await ReadSave(true); else note.Text = live ? "Start RTW3 with the Live Cheats mod enabled, then load a campaign and refresh. Use the floating CHEATS button or F10 while playing." : "No supported campaign saves were found. Save a campaign in RTW3 first.";
        }
        catch (Exception error) { loading = false; Error(error); }
        finally { IsBusy = false; refresh.Enabled = true; UpdateProjectControls(); }
    }

    private async Task ReadSave(bool resetNation)
    {
        Choice save = saves.SelectedItem as Choice;
        if (save == null || IsBusy) return;
        Choice nation = nations.SelectedItem as Choice;
        string id = resetNation || nation == null ? "Nation0" : nation.Id;
        IsBusy = true; apply.Enabled = false; hash = null;
        UpdateProjectControls();
        saves.Enabled = false; nations.Enabled = false; refresh.Enabled = false;
        try
        {
            Dictionary<string, object> response = await backend(live ? new[] { "live-inspect", "--pid", save.Id } : new[] { "cheats-inspect", "--save", save.Id, "--nation", id });
            Populate(response, resetNation);
        }
        catch (Exception error) { Error(error); }
        finally { IsBusy = false; saves.Enabled = true; nations.Enabled = true; refresh.Enabled = true; apply.Enabled = hash != null && (live || !gameRunning); UpdateProjectControls(); }
    }

    private void Populate(Dictionary<string, object> response, bool resetNation)
    {
        loading = true; hash = response["sha256"].ToString();
        bulkAvailable = response.ContainsKey("bulk_projects") && (bool)response["bulk_projects"];
        gameRunning = response.ContainsKey("game_running") && (bool)response["game_running"];
        if (resetNation) {
            nations.Items.Clear();
            foreach (object item in (ArrayList)response["nations"]) { Dictionary<string, object> row = (Dictionary<string, object>)item; nations.Items.Add(new Choice { Id = row["id"].ToString(), Label = row["name"].ToString() }); }
            if (nations.Items.Count > 0) nations.SelectedIndex = 0;
        }
        Dictionary<string, object> values = (Dictionary<string, object>)response["values"];
        researchAll.Tag = null; fastAircraft.Tag = null; technologyBranches.Items.Clear();
        if (live && response.ContainsKey("research_progress")) {
            Dictionary<string, object> research = (Dictionary<string, object>)response["research_progress"];
            if ((bool)research["available"]) {
                researchAll.Tag = true; technologyBar.Value = Convert.ToInt32(research["percent"]);
                technologyText.Text = "Technologies: " + research["completed"] + " / " + research["total"] + " (" + research["percent"] + "%)";
                foreach (Dictionary<string, object> area in ((ArrayList)research["areas"]).Cast<Dictionary<string, object>>())
                    technologyBranches.Items.Add(area["name"] + ": " + area["completed"] + "/" + area["total"] + " (" + area["percent"] + "%)");
                if (technologyBranches.Items.Count > 0) technologyBranches.SelectedIndex = 0;
            } else { technologyBar.Value = 0; technologyText.Text = "Research progress unavailable - restart with mods"; }
        }
        if (live && response.ContainsKey("aircraft_progress")) {
            Dictionary<string, object> aircraft = (Dictionary<string, object>)response["aircraft_progress"];
            if ((bool)aircraft["available"] && ((bool)aircraft["pending_request"] || Convert.ToInt32(aircraft["prototypes"]) > 0)) fastAircraft.Tag = true;
        }
        refillAmmo.Tag = null;
        if (live && response.ContainsKey("battle_ammo")) {
            Dictionary<string, object> ammo = (Dictionary<string, object>)response["battle_ammo"];
            if ((bool)ammo["available"]) refillAmmo.Tag = true;
        }
        refillAmmo.Text = refillAmmo.Tag != null ? "Refill ship ammo ALL" : "Refill ammo - open battle / refresh";
        revealEnemy.Tag = values.ContainsKey("reveal_enemy_ships") ? (object)Convert.ToInt32(values["reveal_enemy_ships"]) : null;
        revealEnemy.Checked = revealEnemy.Tag != null && (int)revealEnemy.Tag == 1;
        revealEnemy.Text = revealEnemy.Tag == null ? "Reveal enemy ships - restart RTW3 with mods to enable" : "Reveal all enemy ships (battle-map markers)";
        forceDaytime.Tag = values.ContainsKey("force_daytime") ? (object)Convert.ToInt32(values["force_daytime"]) : null;
        forceDaytime.Checked = forceDaytime.Tag != null && (int)forceDaytime.Tag == 1;
        forceDaytime.Text = forceDaytime.Tag == null ? "Force daytime - restart RTW3 with mods to enable" : "Force daytime (battle clock keeps running)";
        clearWeather.Tag = values.ContainsKey("clear_weather") ? (object)Convert.ToInt32(values["clear_weather"]) : null;
        clearWeather.Checked = clearWeather.Tag != null && (int)clearWeather.Tag == 1;
        clearWeather.Text = clearWeather.Tag == null ? "Clear weather - restart RTW3 with mods to enable" : "Clear weather / calm seas (both sides)";
        foreach (KeyValuePair<string, NumericUpDown> field in fields) {
            field.Value.Enabled = values.ContainsKey(field.Key);
            if (values.ContainsKey(field.Key)) {
                decimal originalValue = Convert.ToDecimal(values[field.Key]);
                field.Value.Tag = originalValue;
                field.Value.Value = Math.Max(field.Value.Minimum, Math.Min(field.Value.Maximum, originalValue));
                if (originalValue < field.Value.Minimum || originalValue > field.Value.Maximum) field.Value.Enabled = false;
            }
        }
        ships.Items.Clear();
        ArrayList fleet = (ArrayList)(response.ContainsKey("fleet_ships") ? response["fleet_ships"] : response["ships"]);
        foreach (object item in fleet.Cast<Dictionary<string, object>>().OrderBy(row => row["kind"].ToString() == "inactive" ? 1 : 0)) {
            Dictionary<string, object> ship = (Dictionary<string, object>)item;
            string type = ship["type"].ToString(), kind = ship.ContainsKey("kind") ? ship["kind"].ToString() : "build";
            string caption = kind == "refit" ? "refit / repair" : kind == "rebuild" ? "rebuild" : kind == "build" ? "new build" : "no active yard job";
            ships.Items.Add(new Choice { Id = ship["index"] + ":" + ship["remaining_turns"], Kind = kind,
                Label = ship["name"] + (String.IsNullOrWhiteSpace(type) ? "" : " (" + type + ")") + " - " + caption + (kind == "inactive" ? "" : " - " + ship["remaining_turns"] + " turns") });
        }
        shipCaption.Text = (live ? "Player ships: " : "Nation ships: ") + ships.Items.Count + " / Yard jobs: " + ((ArrayList)response["ships"]).Count;
        if (ships.Items.Count > 0) ships.SelectedIndex = 0;
        editShip.Checked = false; UpdateProjectControls();
        loading = false;
        note.Text = response["note"].ToString() + (!live && gameRunning ? "\nRTW3 is running: use LIVE CHEATS, or close the game and refresh this editor before applying saved edits." : "");
        if (live) note.Text += values.ContainsKey("counterintelligence_percent") ?
            "\nCounterintelligence is paid through the native Intelligence line: last calculated cost " + response["counterintelligence_cost"] + "/turn. Each 1% blocks 8% of successful spy operations, up to 80%. Resets at launch." :
            "\nCounterintelligence requires Campaign Security and a restart through Play with mods.";
    }

    private async Task Apply()
    {
        Choice save = saves.SelectedItem as Choice, nation = nations.SelectedItem as Choice;
        if (save == null || nation == null || hash == null || IsBusy) return;
        Dictionary<string, int> values = fields.Where(pair => pair.Value.Enabled && pair.Value.Tag != null && pair.Value.Value != (decimal)pair.Value.Tag).ToDictionary(pair => pair.Key, pair => Decimal.ToInt32(pair.Value.Value));
        if (revealEnemy.Enabled && (revealEnemy.Checked ? 1 : 0) != (int)revealEnemy.Tag) values["reveal_enemy_ships"] = revealEnemy.Checked ? 1 : 0;
        if (forceDaytime.Enabled && (forceDaytime.Checked ? 1 : 0) != (int)forceDaytime.Tag) values["force_daytime"] = forceDaytime.Checked ? 1 : 0;
        if (clearWeather.Enabled && (clearWeather.Checked ? 1 : 0) != (int)clearWeather.Tag) values["clear_weather"] = clearWeather.Checked ? 1 : 0;
        List<string> command = live ? new List<string> { "live-edit", "--pid", save.Id, "--sha", hash, "--values", json.Serialize(values) } : new List<string> { "cheats-edit", "--save", save.Id, "--nation", nation.Id, "--sha", hash, "--values", json.Serialize(values) };
        if (editShip.Checked && editShip.Enabled && ships.SelectedItem != null) { command.Add("--ship-index"); command.Add(((Choice)ships.SelectedItem).Id.Split(':')[0]); command.Add("--turns"); command.Add(buildTurns.Value.ToString()); }
        IsBusy = true; apply.Enabled = false; refresh.Enabled = false; saves.Enabled = false; nations.Enabled = false;
        UpdateProjectControls();
        try
        {
            Dictionary<string, object> result = await backend(command.ToArray());
            Populate((Dictionary<string, object>)result["save"], false);
            note.Text = result["message"] + (result.ContainsKey("backup") ? "\nBackup: " + result["backup"] : "");
        }
        catch (Exception error) { Error(error); }
        finally { IsBusy = false; apply.Enabled = hash != null && (live || !gameRunning); refresh.Enabled = true; saves.Enabled = true; nations.Enabled = true; UpdateProjectControls(); }
    }
}

internal sealed class DecisionEditorPanel : UserControl
{
    private sealed class DecisionChoice
    {
        internal string Id, Name, Mode, Description;
        internal Dictionary<string, object> Data;
        public override string ToString() { return Name; }
    }

    private readonly Func<string[], Task<Dictionary<string, object>>> backend;
    private readonly int pid;
    private readonly ComboBox decisions;
    private readonly TextBox profile;
    private readonly Label detail, status;
    private readonly Button apply, reload;
    private bool busy;
    private int year;
    private string activeId;
    private int paid, duration, lastYear;

    internal DecisionEditorPanel(Func<string[], Task<Dictionary<string, object>>> callback, int processId, string defaultProfile)
    {
        backend = callback; pid = processId;
        Dock = DockStyle.Fill; AutoScroll = true; Padding = new Padding(18);
        BackColor = Color.FromArgb(18, 26, 35); ForeColor = Color.FromArgb(229, 236, 243); Font = new Font("Segoe UI", 10);
        TableLayoutPanel root = new TableLayoutPanel { Dock = DockStyle.Top, Height = 420, ColumnCount = 1, RowCount = 7 };
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 35)); root.RowStyles.Add(new RowStyle(SizeType.Absolute, 35));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 105)); root.RowStyles.Add(new RowStyle(SizeType.Absolute, 90));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 42)); root.RowStyles.Add(new RowStyle(SizeType.Absolute, 42));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100)); Controls.Add(root);
        root.Controls.Add(new Label { Text = "Campaign profile (reuse this name for the same campaign)", AutoSize = true }, 0, 0);
        profile = new TextBox { Dock = DockStyle.Fill, Text = defaultProfile, BackColor = Color.FromArgb(27, 38, 50), ForeColor = ForeColor };
        root.Controls.Add(profile, 0, 1);
        decisions = new ComboBox { Dock = DockStyle.Fill, DropDownStyle = ComboBoxStyle.DropDownList, BackColor = Color.FromArgb(27, 38, 50), ForeColor = ForeColor };
        root.Controls.Add(decisions, 0, 2);
        detail = new Label { Dock = DockStyle.Fill, ForeColor = Color.FromArgb(196, 211, 224), AutoEllipsis = true };
        root.Controls.Add(detail, 0, 3);
        FlowLayoutPanel actions = new FlowLayoutPanel { Dock = DockStyle.Fill };
        apply = new Button { Text = "Apply decision", Width = 190, Height = 34, Enabled = false, BackColor = Color.FromArgb(33, 131, 130), ForeColor = Color.White, FlatStyle = FlatStyle.Flat };
        reload = new Button { Text = "Reload decisions", Width = 160, Height = 34, BackColor = Color.FromArgb(27, 38, 50), ForeColor = ForeColor, FlatStyle = FlatStyle.Flat };
        Button open = new Button { Text = "Edit decision file", Width = 155, Height = 34, BackColor = Color.FromArgb(27, 38, 50), ForeColor = ForeColor, FlatStyle = FlatStyle.Flat };
        actions.Controls.Add(apply); actions.Controls.Add(reload); actions.Controls.Add(open); root.Controls.Add(actions, 0, 4);
        status = new Label { Dock = DockStyle.Fill, ForeColor = Color.FromArgb(155, 174, 191), AutoEllipsis = true };
        root.Controls.Add(status, 0, 5);
        root.Controls.Add(new Label { Dock = DockStyle.Fill, ForeColor = Color.FromArgb(155, 174, 191),
            Text = "One-time decisions apply immediately. Projects charge the first year when started; use the annual installment button after each later year. Save your campaign in RTW3 to keep the changes." }, 0, 6);
        decisions.SelectedIndexChanged += delegate { UpdateSelection(); };
        profile.KeyDown += async delegate(object sender, KeyEventArgs args) {
            if (args.KeyCode == Keys.Enter) { args.SuppressKeyPress = true; await RefreshStatus(); }
        };
        reload.Click += async delegate { await Reload(); };
        apply.Click += async delegate { await ApplySelected(); };
        open.Click += delegate {
            try { Process.Start(new ProcessStartInfo("notepad.exe", "\"" + Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "Mods", "CampaignOverhaul", "custom_decisions.json") + "\"") { UseShellExecute = false }); }
            catch (Exception error) { status.Text = error.Message; }
        };
        Load += async delegate { await Reload(); };
    }

    private async Task Reload()
    {
        if (busy) return; busy = true; apply.Enabled = false; reload.Enabled = false;
        try {
            Dictionary<string, object> response = await backend(new[] { "decision-list" });
            decisions.Items.Clear();
            foreach (object raw in (ArrayList)response["decisions"]) {
                Dictionary<string, object> item = (Dictionary<string, object>)raw;
                decisions.Items.Add(new DecisionChoice { Id = item["id"].ToString(), Name = item["name"].ToString(), Mode = item["mode"].ToString(),
                    Description = item.ContainsKey("description") ? item["description"].ToString() : "", Data = item });
            }
            if (decisions.Items.Count > 0) decisions.SelectedIndex = 0;
            status.Text = "Editable definitions: " + response["file"];
        } catch (Exception error) { status.Text = error.Message; }
        finally { busy = false; reload.Enabled = true; UpdateSelection(); }
        await RefreshStatus();
    }

    private async Task RefreshStatus()
    {
        if (busy || String.IsNullOrWhiteSpace(profile.Text)) return;
        try {
            Dictionary<string, object> response = await backend(new[] { "decision-status", "--pid", pid.ToString(), "--campaign-key", profile.Text.Trim() });
            year = Convert.ToInt32(response["year"]);
            Dictionary<string, object> record = response["progress"] as Dictionary<string, object>;
            Dictionary<string, object> project = record == null ? null : record["project"] as Dictionary<string, object>;
            activeId = project != null && Convert.ToBoolean(project["active"]) ? project["id"].ToString() : null;
            paid = project == null ? 0 : Convert.ToInt32(project["paid"]);
            duration = project == null ? 0 : Convert.ToInt32(project["duration_years"]);
            lastYear = project == null ? 0 : Convert.ToInt32(project["last_year"]);
            status.Text = response["nation"] + " | campaign year " + year + " | funds " + Convert.ToInt64(response["funds"]).ToString("N0") +
                          (activeId == null ? " | no active project" : " | project " + paid + "/" + duration + " installments, last paid " + lastYear);
        } catch (Exception error) { status.Text = error.Message; activeId = null; }
        UpdateSelection();
    }

    private void UpdateSelection()
    {
        DecisionChoice choice = decisions.SelectedItem as DecisionChoice;
        if (choice == null) { apply.Enabled = false; return; }
        detail.Text = choice.Description;
        if (choice.Mode == "instant") { apply.Text = "Apply decision"; apply.Width = 190; apply.Enabled = !busy; }
        else if (activeId == null) { apply.Text = "Start project (first payment now)"; apply.Width = 245; apply.Enabled = !busy; }
        else if (activeId == choice.Id) { apply.Text = "Apply annual installment"; apply.Width = 220; apply.Enabled = !busy && year > lastYear; }
        else { apply.Text = "Another project is active"; apply.Width = 220; apply.Enabled = false; }
    }

    private async Task ApplySelected()
    {
        DecisionChoice choice = decisions.SelectedItem as DecisionChoice;
        if (busy || choice == null) return;
        if (String.IsNullOrWhiteSpace(profile.Text)) { status.Text = "Enter a campaign profile name first."; return; }
        string mode = choice.Mode == "instant" ? "apply" : activeId == choice.Id ? "installment" : "start";
        busy = true; apply.Enabled = false; reload.Enabled = false;
        try {
            Dictionary<string, object> response = await backend(new[] { "decision-apply", "--pid", pid.ToString(), "--campaign-key", profile.Text.Trim(),
                "--decision-id", choice.Id, "--decision-mode", mode });
            status.Text = response["message"].ToString();
        } catch (Exception error) { status.Text = error.Message; }
        finally { busy = false; reload.Enabled = true; UpdateSelection(); }
        await RefreshStatus();
    }
}
