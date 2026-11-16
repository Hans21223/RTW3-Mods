using System;
using System.Collections;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Linq;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

namespace RTW3.Mods
{
    internal sealed class NativeSubmarinePanel : UserControl
    {
        private readonly Func<Dictionary<string,object>> shared;
        private readonly Action<Dictionary<string,object>> applyShared;
        private readonly Action<bool,bool> saveAction;
        private readonly Action<string> report;
        private readonly Func<string[],Task<Dictionary<string,object>>> backend;
        private readonly Dictionary<string,Control> fields=new Dictionary<string,Control>();
        private readonly List<Control> editControls=new List<Control>();
        private readonly Panel[] pages=new Panel[3];
        private readonly Label result=new Label(),limits=new Label();
        private readonly ListBox library=new ListBox();
        private readonly ComboBox templates=new ComboBox();
        private readonly JavaScriptSerializer json=new JavaScriptSerializer();
        private ArrayList layouts;
        private Dictionary<string,object> design;
        private string ident,lastShared;
        private int revision;
        private int shownPage=-1;
        private bool initialized,loading,awaitingShared;
        internal volatile bool IsBusy,IsDirty;
        private DateTime evaluateAt=DateTime.MaxValue;
        internal event Action<Dictionary<string,object>> Evaluated;
        internal string ClassId {get{return ident;}}
        internal int Revision {get{return revision;}}
        internal int FieldCount {get{return fields.Count;}}
        internal int VisiblePageCount {get{return pages.Count(p=>p.Visible);}}
        private sealed class Item {internal Dictionary<string,object> Data;public override string ToString(){return ((Dictionary<string,object>)Data["design"])["name"]+" (revision "+Data["revision"]+")";}}
        private static readonly Color Surface=Color.FromArgb(51,51,51),Field=Color.FromArgb(26,26,26),Ink=Color.FromArgb(198,198,198);

        internal NativeSubmarinePanel(Func<Dictionary<string,object>> nativeShared,Action<Dictionary<string,object>> setShared,Action<bool,bool> save,Action<string> notify,Func<string[],Task<Dictionary<string,object>>> call)
        {
            shared=nativeShared;applyShared=setShared;saveAction=save;report=notify;backend=call;
            BackColor=Surface;ForeColor=Ink;Font=new Font("Tahoma",8.25F);AutoScroll=true;
            TableLayoutPanel root=new TableLayoutPanel {Dock=DockStyle.Fill,ColumnCount=1,RowCount=3,Padding=new Padding(9)};
            root.RowStyles.Add(new RowStyle(SizeType.Percent,100));root.RowStyles.Add(new RowStyle(SizeType.Absolute,130));root.RowStyles.Add(new RowStyle(SizeType.Absolute,95));Controls.Add(root);
            Panel stack=new Panel {Dock=DockStyle.Fill};root.Controls.Add(stack,0,0);
            for(int i=0;i<3;i++){pages[i]=new Panel {Dock=DockStyle.Fill,AutoScroll=true,BackColor=Surface};stack.Controls.Add(pages[i]);}
            TableLayoutPanel machinery=Grid(pages[0]);
            Number(machinery,0,"year","Design year",1901,2030);Combo(machinery,1,"role","Submarine role",new[]{"medium","minelayer","coastal","long-range","missile"});
            Combo(machinery,2,"propulsion","Propulsion layout",new[]{"diesel-electric","aip","nuclear"});Number(machinery,3,"submerged_speed","Submerged speed (knots)",3,45);
            Number(machinery,4,"depth","Design diving depth (m)",30,800);Number(machinery,5,"battery","Battery layout tier",1,4);Number(machinery,6,"reliability","Reliability tier",0,3);
            machinery.Controls.Add(Note("Use the original Class name, Displacement and Speed controls on the left. Speed there is surfaced speed.\n\nLayout weights are mod estimates. Propulsion, diving depth and performance are not new native simulation mechanics."),0,7);machinery.SetColumnSpan(machinery.GetControlFromPosition(0,7),2);
            TableLayoutPanel arms=Grid(pages[1]);Number(arms,0,"torpedo_tubes","Torpedo tubes",0,12);Number(arms,1,"torpedo_load","Torpedoes carried",0,100);Number(arms,2,"missile_cells","Missile cells",0,48);Number(arms,3,"sonar","Sonar tier",0,3);Number(arms,4,"quieting","Quieting tier",0,3);
            arms.Controls.Add(Note("Availability and accuracy are derived from the class layout and can be applied to matching new native boats.\n\nTorpedo quantities, missile cells and quieting are stored in the class, but do not add custom native weapons, targeting or submarine movement. Native role/research rules still apply."),0,5);arms.SetColumnSpan(arms.GetControlFromPosition(0,5),2);
            TableLayoutPanel classes=new TableLayoutPanel {Dock=DockStyle.Fill,ColumnCount=1,RowCount=5};classes.RowStyles.Add(new RowStyle(SizeType.Percent,100));foreach(int h in new[]{26,28,28,32})classes.RowStyles.Add(new RowStyle(SizeType.Absolute,h));pages[2].Controls.Add(classes);
            library.Dock=DockStyle.Fill;library.BackColor=Field;library.ForeColor=Ink;library.BorderStyle=BorderStyle.FixedSingle;library.SelectedIndexChanged+=delegate {if(!loading&&library.SelectedItem!=null){Item item=(Item)library.SelectedItem;if(!CanDiscard())return;ident=item.Data["id"].ToString();revision=Convert.ToInt32(item.Data["revision"]);Load((Dictionary<string,object>)item.Data["design"],false);}};classes.Controls.Add(library,0,0);
            classes.Controls.Add(Note("Starting layouts (fictional, not historical replicas)"),0,1);templates.Dock=DockStyle.Fill;templates.DropDownStyle=ComboBoxStyle.DropDownList;templates.BackColor=Field;templates.ForeColor=Ink;classes.Controls.Add(templates,0,2);
            classes.Controls.Add(Button("New class from layout",delegate {if(layouts!=null&&templates.SelectedIndex>=0&&CanDiscard()){ident=null;revision=0;Load((Dictionary<string,object>)layouts[templates.SelectedIndex],true);}},220),0,3);
            FlowLayoutPanel actions=new FlowLayoutPanel {Dock=DockStyle.Fill,WrapContents=false};actions.Controls.Add(Button("Save as new class",async delegate {ident=null;revision=0;await SaveAsync();},140));actions.Controls.Add(Button("Save and order...",delegate {saveAction(true,true);},140));classes.Controls.Add(actions,0,4);
            result.Dock=DockStyle.Fill;result.ForeColor=Ink;result.UseMnemonic=false;result.Padding=new Padding(3,7,3,3);root.Controls.Add(result,0,1);
            limits.Dock=DockStyle.Fill;limits.ForeColor=Color.FromArgb(190,174,125);limits.UseMnemonic=false;limits.Text="EXPERIMENTAL CLASS MODE\nNative Save and finish saves this submarine class, not a surface ship.\nNative boats receive only class labels, availability and accuracy. Costs, build times, tactical movement and weapon behavior remain native. No .ds surface-ship file is written.";root.Controls.Add(limits,0,2);
            ShowPage(0);
        }

        private Label Note(string text){return new Label {Text=text,AutoSize=true,MaximumSize=new Size(560,0),ForeColor=Ink,Margin=new Padding(3,9,3,5),UseMnemonic=false};}
        private TableLayoutPanel Grid(Panel page){TableLayoutPanel g=new TableLayoutPanel {Dock=DockStyle.Top,AutoSize=true,ColumnCount=2,Padding=new Padding(6)};g.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,60));g.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,40));page.Controls.Add(g);return g;}
        private void Add(TableLayoutPanel table,int row,string key,string label,Control control){table.RowStyles.Add(new RowStyle(SizeType.Absolute,32));table.Controls.Add(new Label {Text=label,Dock=DockStyle.Fill,TextAlign=ContentAlignment.MiddleLeft},0,row);control.Dock=DockStyle.Fill;control.Margin=new Padding(3,4,8,4);control.BackColor=Field;control.ForeColor=Ink;table.Controls.Add(control,1,row);fields[key]=control;editControls.Add(control);NumericUpDown n=control as NumericUpDown;if(n!=null)n.ValueChanged+=delegate{Changed();};ComboBox c=control as ComboBox;if(c!=null)c.SelectedIndexChanged+=delegate{Changed();};}
        private void Number(TableLayoutPanel table,int row,string key,string label,int low,int high){Add(table,row,key,label,new NumericUpDown {Minimum=low,Maximum=high});}
        private void Combo(TableLayoutPanel table,int row,string key,string label,string[] values){ComboBox c=new ComboBox {DropDownStyle=ComboBoxStyle.DropDownList};c.Items.AddRange(values);Add(table,row,key,label,c);}
        private Button Button(string text,Action action,int width){Button b=new Button {Text=text,Width=width,Height=24,Margin=new Padding(0,1,6,1),BackColor=Surface,ForeColor=Ink,FlatStyle=FlatStyle.Flat};b.FlatAppearance.BorderColor=Color.FromArgb(100,100,100);b.Click+=delegate{if(!IsBusy)action();};editControls.Add(b);return b;}
        internal bool CanDiscard(){return !IsBusy&&(!IsDirty||MessageBox.Show("Discard unsaved submarine class changes?","Submarine class",MessageBoxButtons.YesNo,MessageBoxIcon.Question,MessageBoxDefaultButton.Button2)==DialogResult.Yes);}
        private void Changed(){if(loading)return;IsDirty=true;evaluateAt=DateTime.UtcNow.AddMilliseconds(400);}
        internal void RequestEvaluation(){evaluateAt=DateTime.UtcNow;}
        private void Busy(bool value){IsBusy=value;foreach(Control c in editControls)c.Enabled=!value;library.Enabled=templates.Enabled=!value;}
        private Dictionary<string,object> Values(){Dictionary<string,object> values=new Dictionary<string,object>();foreach(var pair in fields){NumericUpDown number=pair.Value as NumericUpDown;values[pair.Key]=number!=null?(object)Decimal.ToInt32(number.Value):pair.Value.Text;}foreach(var pair in shared())values[pair.Key]=pair.Value;return values;}
        private void Load(Dictionary<string,object> value,bool draft){design=new Dictionary<string,object>(value);loading=true;foreach(var pair in fields){NumericUpDown n=pair.Value as NumericUpDown;if(n!=null)n.Value=Convert.ToDecimal(value[pair.Key]);else pair.Value.Text=value[pair.Key].ToString();}loading=false;awaitingShared=true;applyShared(design);IsDirty=draft;evaluateAt=DateTime.UtcNow.AddMilliseconds(200);}
        internal async void Initialize()
        {
            if(initialized){awaitingShared=true;applyShared(design);return;}
            Busy(true);
            try{Dictionary<string,object> catalog=await backend(new[]{"sub-library"});layouts=(ArrayList)catalog["templates"];loading=true;foreach(Dictionary<string,object> row in layouts)templates.Items.Add(row["name"].ToString());templates.SelectedIndex=Math.Min(1,templates.Items.Count-1);Populate(catalog);loading=false;
                if(library.Items.Count>0){Item first=(Item)library.Items[0];ident=first.Data["id"].ToString();revision=Convert.ToInt32(first.Data["revision"]);Load((Dictionary<string,object>)first.Data["design"],false);}else Load((Dictionary<string,object>)layouts[templates.SelectedIndex],true);initialized=true;
            }catch(Exception e){result.Text=e.Message;report(e.Message);}finally{loading=false;Busy(false);}
        }
        private void Populate(Dictionary<string,object> catalog){bool prior=loading;loading=true;library.Items.Clear();foreach(Dictionary<string,object> entry in (ArrayList)catalog["blueprints"]){int n=library.Items.Add(new Item {Data=entry});if(ident!=null&&entry["id"].ToString()==ident)library.SelectedIndex=n;}loading=prior;}
        internal async void PollShared()
        {
            if(!initialized||IsBusy)return;
            try{
                Dictionary<string,object> value=shared();string signature=json.Serialize(value);
                if(awaitingShared){if(value.Any(p=>p.Value.ToString()!=design[p.Key].ToString()))return;awaitingShared=false;lastShared=signature;}
                else if(lastShared!=signature){lastShared=signature;Changed();}
                if(DateTime.UtcNow<evaluateAt)return;evaluateAt=DateTime.MaxValue;Busy(true);
                design=Values();Dictionary<string,object> response=await backend(new[]{"sub-evaluate","--values",json.Serialize(design)});var native=(Dictionary<string,object>)response["native"];
                result.Text=((bool)response["valid"]?"Layout within displacement":"Over allocated - reduce equipment or increase displacement")+"\nEstimated weight: "+response["used_tons"]+" t   |   Remaining: "+response["margin_tons"]+" t\nNative profile: availability "+native["availability"]+", accuracy "+native["accuracy"]+"\nConstruction cost and build time: native role / research rules (not the surface-ship figures).\n"+(IsDirty?"Unsaved class changes.":"Saved class revision "+revision+".");
                if(Evaluated!=null)Evaluated(response);
            }catch(Exception e){result.Text=e.Message;}finally{Busy(false);}
        }
        internal async Task<bool> SaveAsync()
        {
            if(IsBusy)return false;Busy(true);
            try{design=Values();List<string> args=new List<string>{"sub-save","--values",json.Serialize(design)};if(ident!=null)args.AddRange(new[]{"--blueprint-id",ident,"--revision",revision.ToString()});Dictionary<string,object> saved=await backend(args.ToArray());ident=saved["id"].ToString();revision=Convert.ToInt32(saved["revision"]);IsDirty=false;Populate(await backend(new[]{"sub-library"}));result.Text="Submarine class saved. No surface ship or campaign file was created.";report(result.Text);}
            catch(Exception e){result.Text=e.Message;report(e.Message);MessageBox.Show(e.Message,"Submarine class",MessageBoxButtons.OK,MessageBoxIcon.Information);return false;}
            finally{Busy(false);}
            return true;
        }
        internal void ShowPage(int index){index=Math.Max(0,Math.Min(2,index));if(shownPage==index)return;shownPage=index;for(int i=0;i<pages.Length;i++)pages[i].Visible=i==index;pages[index].BringToFront();}
        internal void DrawHull(Graphics graphics,Rectangle bounds)
        {
            graphics.Clear(Color.FromArgb(204,255,255));if(bounds.Width<40||bounds.Height<80)return;
            graphics.SmoothingMode=SmoothingMode.AntiAlias;float cx=bounds.Width/2F,top=45,height=bounds.Height-95,width=Math.Min(70,bounds.Width*0.35F);
            using(Pen axis=new Pen(Color.FromArgb(90,120,120))){graphics.DrawLine(axis,cx,0,cx,bounds.Height);graphics.DrawLine(axis,0,bounds.Height/2,bounds.Width,bounds.Height/2);}
            using(GraphicsPath hull=new GraphicsPath()){hull.AddArc(cx-width/2,top,width,width,180,180);hull.AddLine(cx+width/2,top+width/2,cx+width/2,top+height-width/2);hull.AddArc(cx-width/2,top+height-width,width,width,0,180);hull.CloseFigure();using(SolidBrush fill=new SolidBrush(Color.FromArgb(190,177,142)))graphics.FillPath(fill,hull);using(Pen outline=new Pen(Color.Black))graphics.DrawPath(outline,hull);}
            using(Pen line=new Pen(Color.FromArgb(45,55,55))) {graphics.DrawRectangle(line,cx-10,top+height*0.36F,20,55);int cells=design!=null?Convert.ToInt32(design["missile_cells"]):0;for(int n=0;n<Math.Min(cells,24);n++)graphics.DrawEllipse(line,cx-16+(n%2)*20,top+height*0.55F+(n/2)*10,11,7);graphics.DrawLine(line,cx-width/2-12,top+height-35,cx+width/2+12,top+height-35);}
            using(SolidBrush text=new SolidBrush(Color.Black))graphics.DrawString("Submarine class layout",Font,text,7,bounds.Height-24);
        }
    }
}
