using System;
using System.Collections;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

internal sealed class SubmarineDesigner : UserControl
{
    private readonly Func<string[], Task<Dictionary<string, object>>> backend;
    private readonly bool quiet;
    private readonly Func<string,int,Task<string>> orderNative;
    private readonly JavaScriptSerializer json = new JavaScriptSerializer();
    private readonly Color bg = Color.FromArgb(18,26,35), panel = Color.FromArgb(27,38,50), ink = Color.FromArgb(229,236,243);
    private readonly Dictionary<string, Control> inputs = new Dictionary<string, Control>();
    private readonly List<Button> buttons = new List<Button>();
    private ListBox library;
    private ComboBox templates, saves, nations, boats;
    private TabControl tabs;
    private Label results, campaignNote;
    private Label status;
    private PictureBox drawing;
    private CheckBox adjustBuild;
    private Button apply;
    private ArrayList templateData;
    private Dictionary<string, object> snapshot;
    private string ident;
    private int revision;
    private bool busy, loading, dirty, initialized;
    internal bool IsBusy { get { return busy; } }
    internal int FieldCount { get { return inputs.Count; } }
    internal bool HasEvaluation { get; private set; }
    internal bool HasVisibleLimits { get { return results!=null && results.Text.Contains("DO NOT") || results!=null && results.Text.Contains("not changed"); } }

    private sealed class Choice
    {
        internal string Name;
        internal Dictionary<string, object> Data;
        public override string ToString() { return Name; }
    }

    internal SubmarineDesigner(Func<string[], Task<Dictionary<string, object>>> call, bool suppressDialogs, Func<string,int,Task<string>> order=null)
    {
        backend=call; quiet=suppressDialogs; orderNative=order; Dock=DockStyle.Fill; BackColor=bg; ForeColor=ink;
        Font=new Font("Segoe UI",9F);
        BuildUI();
    }

    private Button Button(string text, Action action, int width)
    {
        Button b=new Button { Text=text, Width=width, Height=33, FlatStyle=FlatStyle.Flat, BackColor=panel, ForeColor=ink, Margin=new Padding(0,3,8,3) };
        b.Click+=delegate { action(); }; buttons.Add(b); return b;
    }

    private ComboBox Combo()
    {
        return new ComboBox { DropDownStyle=ComboBoxStyle.DropDownList, Dock=DockStyle.Fill, BackColor=panel, ForeColor=ink, FlatStyle=FlatStyle.Flat };
    }

    private void BuildUI()
    {
        TableLayoutPanel root=new TableLayoutPanel { Dock=DockStyle.Fill, Padding=new Padding(18), ColumnCount=2, RowCount=2 };
        root.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,205)); root.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));
        root.RowStyles.Add(new RowStyle(SizeType.Percent,100)); root.RowStyles.Add(new RowStyle(SizeType.Absolute,48)); Controls.Add(root);
        TableLayoutPanel left=new TableLayoutPanel { Dock=DockStyle.Fill, ColumnCount=1, RowCount=6, Padding=new Padding(0,0,14,0) };
        left.RowStyles.Add(new RowStyle(SizeType.Absolute,32));left.RowStyles.Add(new RowStyle(SizeType.Percent,100));
        left.RowStyles.Add(new RowStyle(SizeType.Absolute,28));left.RowStyles.Add(new RowStyle(SizeType.Absolute,34));
        left.RowStyles.Add(new RowStyle(SizeType.Absolute,40));left.RowStyles.Add(new RowStyle(SizeType.Absolute,40));root.Controls.Add(left,0,0);
        left.Controls.Add(new Label { Text="SAVED SUBMARINE CLASSES",AutoSize=true,ForeColor=Color.Turquoise,Padding=new Padding(0,5,0,0) },0,0);
        library=new ListBox { Dock=DockStyle.Fill,BackColor=panel,ForeColor=ink,BorderStyle=BorderStyle.None,IntegralHeight=false };
        library.SelectedIndexChanged+=async delegate { if(!loading && library.SelectedItem!=null) await LoadSelected(); };
        left.Controls.Add(library,0,1);
        left.Controls.Add(new Label { Text="Fictional starting layouts",AutoSize=true,Padding=new Padding(0,6,0,0) },0,2);
        templates=Combo();left.Controls.Add(templates,0,3);
        left.Controls.Add(Button("NEW FROM LAYOUT",delegate { NewTemplate(); },185),0,4);
        left.Controls.Add(Button("Refresh class library",async delegate { await InitializeAsync(true); },185),0,5);
        tabs=new TabControl { Dock=DockStyle.Fill };
        TabPage designPage=new TabPage("Class blueprint") { BackColor=bg }, campaignPage=new TabPage("Link to campaign boat") { BackColor=bg };
        tabs.TabPages.AddRange(new[] { designPage,campaignPage });root.Controls.Add(tabs,1,0);
        tabs.SelectedIndexChanged+=async delegate { if(!quiet && tabs.SelectedIndex==1) await LoadSaves(); };
        TableLayoutPanel design=new TableLayoutPanel { Dock=DockStyle.Fill,ColumnCount=1,RowCount=4,Padding=new Padding(12) };
        design.RowStyles.Add(new RowStyle(SizeType.Absolute,273));design.RowStyles.Add(new RowStyle(SizeType.Absolute,103));
        design.RowStyles.Add(new RowStyle(SizeType.Percent,100));design.RowStyles.Add(new RowStyle(SizeType.Absolute,42));designPage.Controls.Add(design);
        TableLayoutPanel fields=new TableLayoutPanel { Dock=DockStyle.Fill,ColumnCount=4,RowCount=8 };
        for(int i=0;i<4;i++) fields.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,i%2==0?29:21));
        for(int i=0;i<8;i++) fields.RowStyles.Add(new RowStyle(SizeType.Absolute,33)); design.Controls.Add(fields,0,0);
        AddText(fields,0,"name","Class name"); AddNumber(fields,1,"year","Design year",1901,2030);
        AddCombo(fields,2,"role","Native role",new[] { "medium","minelayer","coastal","long-range","missile" });
        AddCombo(fields,3,"propulsion","Projected propulsion",new[] { "diesel-electric","aip","nuclear" });
        AddNumber(fields,4,"displacement","Projected tons",100,50000);AddNumber(fields,5,"depth","Projected depth (m)",30,800);
        AddNumber(fields,6,"surface_speed","Surface speed (kn)",4,40);AddNumber(fields,7,"submerged_speed","Submerged speed (kn)",3,45);
        AddNumber(fields,8,"torpedo_tubes","Torpedo tubes",0,12);AddNumber(fields,9,"torpedo_load","Torpedo stowage",0,100);
        AddNumber(fields,10,"missile_cells","Missile cells",0,48);AddNumber(fields,11,"battery","Battery tier (1-4)",1,4);
        AddNumber(fields,12,"sonar","Sonar tier (0-3)",0,3);AddNumber(fields,13,"quieting","Quieting tier (0-3)",0,3);
        AddNumber(fields,14,"reliability","Reliability tier (0-3)",0,3);
        drawing=new PictureBox { Dock=DockStyle.Fill,BackColor=panel };drawing.Paint+=DrawSubmarine;design.Controls.Add(drawing,0,1);
        Panel resultsScroll=TextPanel(out results);
        design.Controls.Add(resultsScroll,0,2);
        FlowLayoutPanel actions=new FlowLayoutPanel { Dock=DockStyle.Fill,WrapContents=false };
        actions.Controls.Add(Button("Evaluate allocation",async delegate { await Evaluate(); },160));
        Button save=Button("SAVE CLASS",async delegate { await Save(); },140);save.BackColor=Color.FromArgb(33,131,130);actions.Controls.Add(save);
        actions.Controls.Add(Button("Save as new class",async delegate { await Save(true); },155));design.Controls.Add(actions,0,3);
        TableLayoutPanel assign=new TableLayoutPanel { Dock=DockStyle.Fill,ColumnCount=1,RowCount=9,Padding=new Padding(16) };
        foreach(int height in new[] { 66,32,37,32,37,32,37,80 }) assign.RowStyles.Add(new RowStyle(SizeType.Absolute,height));
        assign.RowStyles.Add(new RowStyle(SizeType.Percent,100));campaignPage.Controls.Add(assign);
        assign.Controls.Add(new Label { Dock=DockStyle.Fill,Text="EXPERIMENTAL NATIVE SAVE BRIDGE\nBuild a submarine of the matching native role, save and close RTW3, then link a saved class. No new boat is created.",ForeColor=Color.Turquoise },0,0);
        assign.Controls.Add(new Label { Text="Campaign save",Dock=DockStyle.Fill,Padding=new Padding(0,7,0,0) },0,1);
        saves=Combo();assign.Controls.Add(saves,0,2);saves.SelectedIndexChanged+=async delegate { if(!loading) { loading=true;nations.Items.Clear();loading=false;await InspectSave(); } };
        assign.Controls.Add(new Label { Text="Nation",Dock=DockStyle.Fill,Padding=new Padding(0,7,0,0) },0,3);
        nations=Combo();assign.Controls.Add(nations,0,4);nations.SelectedIndexChanged+=async delegate { if(!loading) await InspectSave(); };
        assign.Controls.Add(new Label { Text="Existing, unsunk submarine",Dock=DockStyle.Fill,Padding=new Padding(0,7,0,0) },0,5);
        boats=Combo();assign.Controls.Add(boats,0,6);
        FlowLayoutPanel applyRow=new FlowLayoutPanel { Dock=DockStyle.Fill,FlowDirection=FlowDirection.TopDown,WrapContents=false };
        adjustBuild=new CheckBox { Text="Also adjust remaining construction turns (building boats only)",AutoSize=true,ForeColor=ink };
        applyRow.Controls.Add(adjustBuild);apply=Button("BACK UP & APPLY PROFILE",async delegate { await Apply(); },255);apply.BackColor=Color.FromArgb(33,131,130);applyRow.Controls.Add(apply);assign.Controls.Add(applyRow,0,7);
        Panel campaignScroll=TextPanel(out campaignNote);
        campaignNote.Text="Only native availability, accuracy and optional construction turns are applied. Names, native role and IDs stay unchanged.\n\nProjected displacement, propulsion, speed, depth and weapon counts are stored in the linked blueprint, but DO NOT change native tactical behavior or the fixed submarine tonnage/cost tables. Direct battle controls are not implemented yet.\n\nEvery apply backs up the whole slot. The linked class snapshot is stored beside the campaign, so later class edits do not silently change an assigned boat.";
        assign.Controls.Add(campaignScroll,0,8);
        if(orderNative!=null) {
            tabs.TabPages.Remove(campaignPage);
            TabPage buildPage=new TabPage("Build in this campaign") { BackColor=bg,Padding=new Padding(24) };
            tabs.TabPages.Add(buildPage);
            FlowLayoutPanel live=new FlowLayoutPanel { Dock=DockStyle.Fill,FlowDirection=FlowDirection.TopDown,WrapContents=false };
            live.Controls.Add(new Label { AutoSize=true,MaximumSize=new Size(680,0),Text="NATIVE CAMPAIGN CONSTRUCTION\n\nSave your class, then open RTW3's normal submarine order dialog here. Choose the matching native role in that dialog. Its research checks, price, quantity and Cancel button remain in control.\n\nBoats created during this order receive the selected class label, availability and accuracy. Native displacement, propulsion, speed, depth, armament, construction cost and build time are NOT changed. The other blueprint fields are projections only.\n\nThis is limited class integration, not a new tactical submarine simulation. Save normally in RTW3 to keep newly ordered boats.",ForeColor=ink,Margin=new Padding(0,0,0,24) });
            Button order=Button("ORDER SELECTED CLASS IN RTW3",async delegate { await OrderNative(); },330);
            order.BackColor=Color.FromArgb(33,131,130);live.Controls.Add(order);buildPage.Controls.Add(live);
        }
        status=new Label { Dock=DockStyle.Fill,AutoEllipsis=true,Padding=new Padding(0,8,0,0),Text="Submarine designer: experimental model, limited native integration." };
        root.Controls.Add(status,0,1);root.SetColumnSpan(status,2);
    }

    private Panel TextPanel(out Label text)
    {
        Panel scroll=new Panel { Dock=DockStyle.Fill,BackColor=panel,AutoScroll=true };
        Label content=new Label { AutoSize=true,Location=new Point(8,6),ForeColor=ink,Font=Font,MaximumSize=new Size(650,0),UseMnemonic=false };
        scroll.Controls.Add(content);scroll.Resize+=delegate { content.MaximumSize=new Size(Math.Max(100,scroll.ClientSize.Width-26),0); };
        text=content;return scroll;
    }

    private void Field(TableLayoutPanel table,int slot,string key,string label,Control control)
    {
        int col=(slot%2)*2,row=slot/2;
        table.Controls.Add(new Label { Text=label,Dock=DockStyle.Fill,TextAlign=ContentAlignment.MiddleLeft },col,row);
        control.Dock=DockStyle.Fill;control.Margin=new Padding(2,3,12,3);control.AccessibleName=label;table.Controls.Add(control,col+1,row);inputs[key]=control;
        TextBox text=control as TextBox;NumericUpDown number=control as NumericUpDown;ComboBox combo=control as ComboBox;
        if(text!=null)text.TextChanged+=delegate { Changed(); };
        if(number!=null)number.ValueChanged+=delegate { Changed(); };
        if(combo!=null)combo.SelectedIndexChanged+=delegate { Changed(); };
    }
    private void AddText(TableLayoutPanel t,int slot,string key,string label) { Field(t,slot,key,label,new TextBox { BackColor=panel,ForeColor=ink,MaxLength=80 }); }
    private void AddNumber(TableLayoutPanel t,int slot,string key,string label,int low,int high) { Field(t,slot,key,label,new NumericUpDown { Minimum=low,Maximum=high,BackColor=panel,ForeColor=ink,ThousandsSeparator=true }); }
    private void AddCombo(TableLayoutPanel t,int slot,string key,string label,string[] values) { ComboBox c=Combo();c.Items.AddRange(values);Field(t,slot,key,label,c); }
    private void Changed() { if(loading)return;dirty=true;HasEvaluation=false;status.Text="Unsaved blueprint changes. Evaluate or save to recalculate. Native campaign is unchanged.";if(drawing!=null)drawing.Invalidate(); }
    private Dictionary<string,object> Values()
    {
        Dictionary<string,object> data=new Dictionary<string,object>();
        foreach(var pair in inputs) { NumericUpDown number=pair.Value as NumericUpDown;data[pair.Key]=number!=null?(object)Decimal.ToInt32(number.Value):pair.Value.Text; }
        return data;
    }
    private void SetValues(Dictionary<string,object> data)
    {
        loading=true;
        foreach(var pair in inputs) { NumericUpDown number=pair.Value as NumericUpDown;if(number!=null)number.Value=Convert.ToDecimal(data[pair.Key]);else pair.Value.Text=data[pair.Key].ToString(); }
        loading=false;dirty=false;HasEvaluation=false;drawing.Invalidate();
    }
    internal bool ConfirmDiscard()
    {
        return !dirty || quiet || MessageBox.Show(this,"Discard unsaved submarine blueprint changes?","Submarine designer",MessageBoxButtons.YesNo,MessageBoxIcon.Question,MessageBoxDefaultButton.Button2)==DialogResult.Yes;
    }
    private void Busy(bool value) { busy=value;foreach(Button b in buttons)b.Enabled=!value;library.Enabled=!value;templates.Enabled=!value;foreach(Control c in inputs.Values)c.Enabled=!value;saves.Enabled=!value;nations.Enabled=!value;boats.Enabled=!value;adjustBuild.Enabled=!value;if(!value)apply.Enabled=snapshot!=null && !(bool)snapshot["game_running"]; }
    private void Failure(Exception error) { status.Text="Stopped: "+error.Message;if(!quiet)MessageBox.Show(this,error.Message,"Submarine designer",MessageBoxButtons.OK,MessageBoxIcon.Information); }

    internal async Task InitializeAsync(bool force=false)
    {
        if(busy || (initialized && !force))return;
        if(initialized && !ConfirmDiscard())return;
        Busy(true);
        try {
            Dictionary<string,object> response=await backend(new[] { "sub-library" });
            loading=true;library.Items.Clear();templates.Items.Clear();templateData=(ArrayList)response["templates"];
            foreach(Dictionary<string,object> entry in (ArrayList)response["blueprints"])library.Items.Add(new Choice { Name=((Dictionary<string,object>)entry["design"])["name"].ToString()+"  /  r"+entry["revision"],Data=entry });
            foreach(Dictionary<string,object> entry in templateData)templates.Items.Add(entry["name"].ToString());
            templates.SelectedIndex=Math.Min(1,templates.Items.Count-1);loading=false;
            if(library.Items.Count>0) { loading=true;library.SelectedIndex=0;loading=false;Choice selected=(Choice)library.SelectedItem;ident=selected.Data["id"].ToString();revision=Convert.ToInt32(selected.Data["revision"]);SetValues((Dictionary<string,object>)selected.Data["design"]); }
            else { ident=null;revision=0;SetValues((Dictionary<string,object>)templateData[templates.SelectedIndex]); }
            initialized=true;
        } catch(Exception e) { loading=false;Failure(e); } finally { Busy(false); }
        if(initialized)await Evaluate();
    }
    private async Task LoadSelected()
    {
        if(busy)return;
        if(!ConfirmDiscard()) {
            loading=true;library.ClearSelected();
            if(ident!=null)for(int i=0;i<library.Items.Count;i++)if(((Choice)library.Items[i]).Data["id"].ToString()==ident)library.SelectedIndex=i;
            loading=false;return;
        }
        Choice selected=(Choice)library.SelectedItem;if(selected==null)return;
        ident=selected.Data["id"].ToString();revision=Convert.ToInt32(selected.Data["revision"]);SetValues((Dictionary<string,object>)selected.Data["design"]);await Evaluate();
    }
    private async void NewTemplate()
    {
        if(busy || templateData==null || templates.SelectedIndex<0 || !ConfirmDiscard())return;
        ident=null;revision=0;loading=true;library.ClearSelected();loading=false;SetValues((Dictionary<string,object>)templateData[templates.SelectedIndex]);dirty=true;tabs.SelectedIndex=0;await Evaluate();
    }
    private async Task Evaluate()
    {
        if(busy)return;Busy(true);
        try {
            Dictionary<string,object> response=await backend(new[] { "sub-evaluate","--values",json.Serialize(Values()) });
            Dictionary<string,object> native=(Dictionary<string,object>)response["native"];
            StringBuilder text=new StringBuilder();text.AppendLine((bool)response["valid"]?"ALLOCATION WITHIN BLUEPRINT TONNAGE":"OVER ALLOCATION - cannot save or apply");
            text.AppendLine("Estimated allocated: "+response["used_tons"]+" t  |  Margin: "+response["margin_tons"]+" t");
            text.AppendLine("Native profile: availability "+native["availability"]+", accuracy tier "+native["accuracy"]+", suggested build turns "+native["suggested_build_turns"]+".");
            foreach(object warning in (ArrayList)response["warnings"]) { text.AppendLine();text.AppendLine(orderNative!=null?warning.ToString().Replace("The native bridge applies availability, accuracy and optional remaining construction turns only.","In-game orders apply the class label, availability and accuracy only. Native build times are unchanged."):warning.ToString()); }
            results.Text=text.ToString();HasEvaluation=true;status.Text=ident==null?"Draft class. Save it before ordering.":"Class revision "+revision+". Save changes before ordering or applying.";
        } catch(Exception e) { Failure(e); } finally { Busy(false); }
    }
    private async Task Save(bool asNew=false)
    {
        if(busy)return;Busy(true);
        try {
            List<string> args=new List<string> { "sub-save","--values",json.Serialize(Values()) };
            if(!asNew && ident!=null)args.AddRange(new[] { "--blueprint-id",ident,"--revision",revision.ToString() });
            Dictionary<string,object> response=await backend(args.ToArray());ident=response["id"].ToString();revision=Convert.ToInt32(response["revision"]);dirty=false;
            status.Text=response["message"].ToString();
            Dictionary<string,object> catalog=await backend(new[] { "sub-library" });loading=true;library.Items.Clear();
            foreach(Dictionary<string,object> row in (ArrayList)catalog["blueprints"]) { int i=library.Items.Add(new Choice { Name=((Dictionary<string,object>)row["design"])["name"].ToString()+"  /  r"+row["revision"],Data=row });if(row["id"].ToString()==ident)library.SelectedIndex=i; } loading=false;
        } catch(Exception e) { loading=false;Failure(e); } finally { Busy(false); }
        await Evaluate();
    }
    private async Task OrderNative()
    {
        if(busy || orderNative==null)return;
        if(ident==null || dirty) { Failure(new Exception("Save the selected class before ordering submarines."));return; }
        if(quiet)return;
        Busy(true);
        try { status.Text=await orderNative(ident,revision); }
        catch(Exception e) { Failure(e); }
        finally { Busy(false); }
    }
    internal async Task InitializeCampaignAsync() { await LoadSaves(); }
    private async Task LoadSaves()
    {
        if(busy)return;Busy(true);
        try { Dictionary<string,object> response=await backend(new[] { "cheats-list" });loading=true;saves.Items.Clear();
            foreach(Dictionary<string,object> row in (ArrayList)response["saves"])saves.Items.Add(new Choice { Name=row["name"].ToString(),Data=row });
            if(saves.Items.Count>0)saves.SelectedIndex=0;loading=false;
        }catch(Exception e){loading=false;Failure(e);}finally{Busy(false);}
        if(saves.SelectedItem!=null)await InspectSave();
    }
    private async Task InspectSave()
    {
        if(busy || saves.SelectedItem==null)return;
        Busy(true);snapshot=null;boats.Items.Clear();
        try {
            string nation=nations.SelectedItem==null?"Nation0":((Choice)nations.SelectedItem).Data["id"].ToString();
            Dictionary<string,object> response=await backend(new[] { "sub-inspect","--save",((Choice)saves.SelectedItem).Data["path"].ToString(),"--nation",nation });
            loading=true;nations.Items.Clear();
            foreach(Dictionary<string,object> row in (ArrayList)response["nations"]) { int i=nations.Items.Add(new Choice { Name=row["name"].ToString(),Data=row });if(row["id"].ToString()==nation)nations.SelectedIndex=i; }
            foreach(Dictionary<string,object> row in (ArrayList)response["boats"])boats.Items.Add(new Choice { Name=row["name"]+"  /  "+row["role"]+"  /  "+row["remaining_turns"]+" turns remaining",Data=row });
            if(boats.Items.Count>0)boats.SelectedIndex=0;snapshot=response;loading=false;
            status.Text=(bool)response["game_running"]?"RTW3 is running: blueprint design is available, but save application is disabled. Close the game, then reload this tab.":boats.Items.Count==0?"No unsunk submarines in this nation/save. Choose another campaign or build a matching native boat first.":"Campaign submarines loaded. Choose a saved class and matching native role.";
        }catch(Exception e){loading=false;Failure(e);}finally{Busy(false);}
    }
    private async Task Apply()
    {
        if(busy)return;
        if(ident==null || dirty || snapshot==null || boats.SelectedItem==null) { Failure(new Exception("Save the class and select a campaign submarine first."));return; }
        if(!quiet && MessageBox.Show(this,"Back up the full slot and apply availability, accuracy"+(adjustBuild.Checked?" and remaining build turns":"")+"?\n\nProjected displacement, speed, depth and weapons do not change native tactical behavior. Reload the campaign afterward.","Apply experimental submarine profile",MessageBoxButtons.YesNo,MessageBoxIcon.Warning,MessageBoxDefaultButton.Button2)!=DialogResult.Yes)return;
        if(quiet)return; // Render/self-tests never write a campaign.
        Busy(true);
        try {
            List<string> args=new List<string> { "sub-apply","--save",snapshot["path"].ToString(),"--nation",snapshot["nation"].ToString(),"--sha",snapshot["sha256"].ToString(),"--sub-index",((Choice)boats.SelectedItem).Data["index"].ToString(),"--blueprint-id",ident,"--revision",revision.ToString() };
            if(adjustBuild.Checked)args.Add("--adjust-build");Dictionary<string,object> response=await backend(args.ToArray());snapshot=(Dictionary<string,object>)response["save"];status.Text=response["message"].ToString()+" Backup: "+response["backup"];
        }catch(Exception e){Failure(e);}finally{Busy(false);}
    }
    private void DrawSubmarine(object sender,PaintEventArgs e)
    {
        e.Graphics.SmoothingMode=SmoothingMode.AntiAlias;int w=drawing.Width,h=drawing.Height;if(w<100 || h<40)return;
        float x=26,y=h*0.48F,width=w-52,height=31;
        using(Pen p=new Pen(Color.FromArgb(91,192,187),2))using(SolidBrush fill=new SolidBrush(Color.FromArgb(45,73,86))) {
            GraphicsPath hull=new GraphicsPath();hull.AddArc(x,y-height/2,height,height,90,180);hull.AddLine(x+height/2,y-height/2,x+width-height/2,y-height/2);hull.AddArc(x+width-height,y-height/2,height,height,270,180);hull.CloseFigure();e.Graphics.FillPath(fill,hull);e.Graphics.DrawPath(p,hull);hull.Dispose();
            e.Graphics.FillRectangle(fill,x+width*0.40F,y-height/2-17,44,17);e.Graphics.DrawRectangle(p,x+width*0.40F,y-height/2-17,44,17);
            int cells=Convert.ToInt32(((NumericUpDown)inputs["missile_cells"]).Value);for(int i=0;i<Math.Min(cells,12);i++)e.Graphics.DrawRectangle(p,x+width*0.53F+(i%6)*14,y-8+(i/6)*10,8,6);
            int tubes=Convert.ToInt32(((NumericUpDown)inputs["torpedo_tubes"]).Value);for(int i=0;i<Math.Min(tubes,6);i++)e.Graphics.DrawLine(p,x+5,y-10+i*4,x+24,y-10+i*4);
            e.Graphics.DrawLine(p,x+width,y-14,x+width,y+14);e.Graphics.DrawLine(p,x+width-6,y,x+width+8,y);
        }
        using(SolidBrush brush=new SolidBrush(ink))e.Graphics.DrawString("BLUEPRINT SCHEMATIC - projected layout, not a native tactical hull",Font,brush,18,h-23);
    }
}
