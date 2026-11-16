// Isolated UI fixture. Compile with CheatMenu.cs, not the production entrypoint.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

internal sealed partial class CampaignEditorPanel
{
    private static void Check(bool value, string message) { if (!value) throw new Exception(message); }

    internal static async Task TestShortcuts(string preview)
    {
        JavaScriptSerializer serializer = new JavaScriptSerializer();
        int writes = 0;
        Dictionary<string, object> fixture = serializer.Deserialize<Dictionary<string, object>>(
            "{\"sha256\":\"fixture-only\",\"bulk_projects\":true,\"counterintelligence_cost\":0,\"values\":{\"funds\":1000,\"reveal_enemy_ships\":0,\"force_daytime\":0,\"clear_weather\":0,\"counterintelligence_percent\":0},\"nations\":[{\"id\":\"Player\",\"name\":\"Fixture nation\"}]," +
            "\"ships\":[{\"index\":0,\"name\":\"Fixture build\",\"type\":\"BB\",\"kind\":\"build\",\"remaining_turns\":15}," +
            "{\"index\":1,\"name\":\"Fixture refit\",\"type\":\"CA\",\"kind\":\"refit\",\"remaining_turns\":3}," +
            "{\"index\":2,\"name\":\"Fixture rebuild\",\"type\":\"BB\",\"kind\":\"rebuild\",\"remaining_turns\":12}]," +
            "\"note\":\"FIXTURE PREVIEW - not a real campaign. Select a project, stage a fast option, then Apply.\"}");
        fixture["research_progress"] = serializer.Deserialize<Dictionary<string, object>>("{\"available\":true,\"completed\":1,\"total\":2,\"percent\":50,\"areas\":[{\"name\":\"Fixture machinery\",\"completed\":1,\"total\":2,\"percent\":50}]}");
        fixture["aircraft_progress"] = serializer.Deserialize<Dictionary<string, object>>("{\"available\":true,\"pending_request\":true,\"prototypes\":1}");
        fixture["battle_ammo"] = serializer.Deserialize<Dictionary<string, object>>("{\"available\":true}");
        Func<string[], Task<Dictionary<string, object>>> callback = args => {
            if (args[0].EndsWith("-list")) return Task.FromResult(serializer.Deserialize<Dictionary<string, object>>(
                "{\"saves\":[{\"path\":\"42\",\"name\":\"Fixture session - no game writes\"}]}"));
            if (args[0].EndsWith("-inspect")) return Task.FromResult(fixture);
            writes++;
            if (Array.IndexOf(args, "--ship-index") >= 0)
                Check(args[Array.IndexOf(args, "--turns")+1] == "1", "Shortcut did not submit one turn.");
            else if (Array.IndexOf(args, "--all-projects") >= 0)
            {
                Check(args[Array.IndexOf(args, "--all-projects")+1] == "build" || args[Array.IndexOf(args, "--all-projects")+1] == "refit", "Invalid bulk project mode.");
                Check(args[Array.IndexOf(args, "--values")+1] == "{}", "Bulk click applied unrelated pending values.");
                Check(Array.IndexOf(args, "--ship-index") < 0, "Bulk click applied an unrelated selected-ship edit.");
            }
            else if (Array.IndexOf(args, "--action") >= 0) {
                Check(args[Array.IndexOf(args, "--action")+1] == "research-all" || args[Array.IndexOf(args, "--action")+1] == "fast-aircraft" || args[Array.IndexOf(args, "--action")+1] == "refill-ammo", "Invalid quick action.");
                Check(args[Array.IndexOf(args, "--values")+1] == "{}", "Quick action applied unrelated pending values.");
            }
            else if (args[Array.IndexOf(args, "--values")+1].Contains("counterintelligence_percent"))
                Check(args[0] == "live-edit", "Counterintelligence must be live-only.");
            else if (args[Array.IndexOf(args, "--values")+1].Contains("force_daytime"))
                Check(args[0] == "live-edit" && args[Array.IndexOf(args, "--values")+1].Contains("\"force_daytime\":1") && args[Array.IndexOf(args, "--values")+1].Contains("\"clear_weather\":1"), "Environment settings were not submitted together.");
            else Check(args[0] == "live-edit" && args[Array.IndexOf(args, "--values")+1].Contains("\"reveal_enemy_ships\":1"), "Reveal not submitted as a live-only value.");
            return Task.FromResult(new Dictionary<string, object> { { "save", fixture }, { "message", "Fixture commit only" } });
        };
        foreach (bool isLive in new[] { true, false }) {
            fixture.Remove("fleet_ships");
            using (Form host = new Form { Size = new Size(795, 865), Opacity = 0, ShowInTaskbar = false })
            using (CampaignEditorPanel editor = new CampaignEditorPanel(callback, isLive, true)) {
                host.Controls.Add(editor); host.Show();
                await editor.InitializeAsync(true);
                Check(editor.fastBuildAll.Enabled && editor.fastRefitAll.Enabled, "All-ships shortcuts unavailable.");
                if (isLive) Check(editor.fields["counterintelligence_percent"].Enabled, "Counterintelligence unavailable.");
                Check(editor.researchAll.Enabled == isLive && editor.fastAircraft.Enabled == isLive, "Research / aircraft quick-action state wrong.");
                if (isLive) Check(editor.technologyBar.Value == 50 && editor.technologyBranches.Items.Count == 1, "Technology progress did not render.");
                Check(editor.revealEnemy.Enabled == isLive, "Battle reveal must be live-only.");
                Check(editor.forceDaytime.Enabled == isLive && editor.clearWeather.Enabled == isLive, "Environment settings must be live-only.");
                Check(editor.refillAmmo.Enabled == isLive, "Ammo refill must be live-only.");
                Check(editor.clearWeather.Bottom <= editor.clearWeather.Parent.ClientSize.Height, "Environment settings are clipped.");
                if (isLive) Check(editor.refillAmmo.Bottom <= editor.refillAmmo.Parent.ClientSize.Height, "Ammo refill button is clipped.");
                Check(editor.fastBuild.Enabled && !editor.fastRefit.Enabled, "Build shortcut state wrong.");
                int before = writes;
                editor.fastBuild.PerformClick();
                Check(editor.editShip.Checked && editor.buildTurns.Value == 1 && writes == before, "Build staging wrote prematurely.");
                await editor.Apply(); Check(writes == before+1, "Apply did not use the backend.");
                editor.ships.SelectedIndex = 1;
                Check(!editor.editShip.Checked && !editor.fastBuild.Enabled && editor.fastRefit.Enabled, "Refit selection retained an old staged edit.");
                Check(editor.buildTurns.Maximum == 99, "Native countdown sentinel values allowed.");
                editor.fastRefit.PerformClick();
                Check(editor.editShip.Checked && editor.buildTurns.Value == 1 && writes == before+1, "Refit staging wrong.");
                if (isLive) {
                    host.PerformLayout(); editor.PerformLayout();
                    Check(editor.fastRefit.Visible && editor.apply.Visible, "Shortcut buttons not visible.");
                    Check(editor.fastRefit.Bottom <= editor.fastRefit.Parent.ClientSize.Height, "Shortcut row is clipped.");
                    using (Bitmap bitmap = new Bitmap(host.Width, host.Height)) {
                        host.DrawToBitmap(bitmap, new Rectangle(Point.Empty, host.Size)); bitmap.Save(preview);
                    }
                }
                await editor.Apply(); Check(writes == before+2, "Refit Apply failed.");
                if (isLive) {
                    editor.revealEnemy.Checked = true;
                    Check(writes == before+2, "Reveal checkbox wrote before Apply.");
                    await editor.Apply(); Check(writes == before+3, "Reveal Apply failed.");
                    Dictionary<string, object> values = (Dictionary<string, object>)fixture["values"];
                    values.Remove("reveal_enemy_ships"); editor.Populate(fixture, false);
                    Check(!editor.revealEnemy.Enabled, "Old sessions must require a restart for reveal.");
                    values["reveal_enemy_ships"] = 0; editor.Populate(fixture, false);
                    editor.forceDaytime.Checked = true; editor.clearWeather.Checked = true;
                    int prior = writes;
                    Check(writes == before+3, "Environment checkbox wrote before Apply.");
                    await editor.Apply(); Check(writes == prior+1, "Environment Apply failed.");
                    values.Remove("force_daytime"); values.Remove("clear_weather"); editor.Populate(fixture, false);
                    Check(!editor.forceDaytime.Enabled && !editor.clearWeather.Enabled, "Old sessions must require a restart for environment settings.");
                    values["force_daytime"] = 0; values["clear_weather"] = 0; editor.Populate(fixture, false);
                }
                editor.ships.SelectedIndex = 2;
                Check(editor.fastRefit.Enabled && !editor.fastBuild.Enabled && editor.buildTurns.Maximum == 1200, "Major rebuild shortcut wrong.");
                fixture["game_running"] = true;
                editor.Populate(fixture, false);
                Check(isLive || (!editor.fastBuild.Enabled && !editor.fastRefit.Enabled), "Saved shortcuts enabled with game running.");
                fixture.Remove("game_running");
                ArrayList rows = (ArrayList)fixture["ships"];
                fixture["ships"] = new ArrayList(); editor.Populate(fixture, false);
                Check(!editor.fastBuild.Enabled && !editor.fastRefit.Enabled, "Empty project list enabled shortcuts.");
                fixture["ships"] = rows;
                ArrayList roster = new ArrayList(rows);
                roster.Add(serializer.Deserialize<Dictionary<string, object>>("{\"index\":3,\"name\":\"Fixture serving ship\",\"type\":\"DD\",\"kind\":\"inactive\",\"remaining_turns\":0}"));
                fixture["fleet_ships"] = roster;
                editor.Populate(fixture, false);
                Check(editor.ships.Items.Count == 4 && editor.shipCaption.Text.Contains("4"), "Fleet list hid non-project ships.");
                editor.ships.SelectedIndex = 3;
                Check(!editor.fastBuild.Enabled && !editor.fastRefit.Enabled && !editor.editShip.Enabled, "Serving ship can be edited as a yard job.");
                Check(editor.fastBuildAll.Enabled && editor.fastRefitAll.Enabled, "Non-project selection disabled ALL actions.");
                if (isLive) {
                    editor.note.Text = "FIXTURE ONLY - serving ships remain visible; ALL buttons apply their own action directly. No real game writes.";
                    using (Bitmap bitmap = new Bitmap(host.Width, host.Height)) {
                        host.DrawToBitmap(bitmap, new Rectangle(Point.Empty, host.Size)); bitmap.Save(preview);
                    }
                }
                editor.fields["funds"].Value = 2000;
                if (isLive) { editor.forceDaytime.Checked = true; editor.clearWeather.Checked = true; }
                foreach (string kind in new[] { "build", "refit" }) {
                    int prior = writes;
                    (kind == "build" ? editor.fastBuildAll : editor.fastRefitAll).PerformClick();
                    // Fixture callbacks complete synchronously, exercising the
                    // actual button event, not a direct call to Apply.
                    Check(writes == prior+1 && !editor.IsBusy, "Bulk button did not apply immediately.");
                    Check(editor.fields["funds"].Value == 2000 && (decimal)editor.fields["funds"].Tag == 1000, "Bulk action lost pending funds or treated them as applied.");
                    if (isLive) Check(editor.forceDaytime.Checked && editor.clearWeather.Checked, "Bulk action lost pending environment settings.");
                }
                editor.fields["funds"].Value = 1000;
                if (isLive) {
                    editor.fields["funds"].Value = 2000;
                    foreach (Button button in new[] { editor.researchAll, editor.fastAircraft, editor.refillAmmo }) {
                        int prior = writes; button.PerformClick();
                        Check(writes == prior+1 && !editor.IsBusy, "Research / aircraft button did not apply on click.");
                        Check(editor.fields["funds"].Value == 2000 && (decimal)editor.fields["funds"].Tag == 1000, "Quick action lost pending funds.");
                        Check(editor.forceDaytime.Checked && editor.clearWeather.Checked, "Quick action lost pending environment settings.");
                    }
                    editor.fields["funds"].Value = 1000;
                    fixture["battle_ammo"] = serializer.Deserialize<Dictionary<string, object>>("{\"available\":false}");
                    editor.Populate(fixture, false);
                    Check(!editor.refillAmmo.Enabled, "Ammo refill is enabled outside a battle.");
                    fixture["battle_ammo"] = serializer.Deserialize<Dictionary<string, object>>("{\"available\":true}");
                    editor.Populate(fixture, false);
                }
                // An all-serving fleet remains visible, with clear disabled
                // shortcuts instead of an empty/misleading ship selector.
                fixture["ships"] = new ArrayList(); fixture["fleet_ships"] = new ArrayList { roster[3] };
                editor.Populate(fixture, false);
                Check(editor.ships.Items.Count == 1 && editor.ships.Enabled, "Serving-only fleet is hidden.");
                Check(!editor.fastBuildAll.Enabled && !editor.fastRefitAll.Enabled, "Serving-only fleet allows invalid bulk edits.");
                fixture["ships"] = rows; fixture["fleet_ships"] = roster;
                editor.Populate(fixture, false);
                if (isLive) {
                    editor.fields["counterintelligence_percent"].Value = 2;
                    await editor.Apply();
                }
                host.Hide();
            }
        }
    }
}

internal static class CheatMenuSelfTest
{
    [STAThread]
    private static void Main()
    {
        Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
        Form runner = new Form { Opacity = 0, ShowInTaskbar = false };
        runner.Shown += async delegate {
            string root = AppDomain.CurrentDomain.BaseDirectory;
            try {
                await CampaignEditorPanel.TestShortcuts(Path.Combine(root, "fast-cheats-fixture-preview.png"));
                File.WriteAllText(Path.Combine(root, "fast-cheats-ui-test.json"), "{\"ok\":true,\"fixture_only\":true,\"real_game_writes\":false,\"live_and_saved_shortcuts\":true,\"bulk_buttons_apply_immediately\":true,\"research_aircraft_buttons_apply_immediately\":true,\"technology_progress_visible\":true,\"pending_values_preserved\":true,\"nonproject_ships_visible\":true,\"environment_apply_and_restart_guard\":true}");
            }
            catch (Exception e) {
                File.WriteAllText(Path.Combine(root, "fast-cheats-ui-test.json"), new JavaScriptSerializer().Serialize(new { ok=false, error=e.ToString() }));
                Environment.ExitCode = 1;
            }
            finally { runner.Close(); }
        };
        Application.Run(runner);
    }
}
