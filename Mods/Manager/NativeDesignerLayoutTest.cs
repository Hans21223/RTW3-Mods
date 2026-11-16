using System;
using System.Collections;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

namespace RTW3.Mods
{
    // Tests only the embedded subsystem component. It does not pretend to be
    // the original game form or verify its message routing / save lifecycle.
    internal static class NativeDesignerLayoutTest
    {
        [STAThread]
        private static void Main(string[] args)
        {
            string game=Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"..",".."));
            Form form=new Form {Text="Subsystem layout test - NOT an RTW3 game screenshot",Size=new Size(690,700),ShowInTaskbar=false,Opacity=0};
            Dictionary<string,object> shared=new Dictionary<string,object>{{"name","Layout test"},{"displacement",1500},{"surface_speed",18}};
            Func<string[],Task<Dictionary<string,object>>> backend=async values=>{
                if(values[0]!="sub-library"&&values[0]!="sub-evaluate")throw new Exception("Layout tests are read-only.");
                Dictionary<string,object> response=await BackendClient.CallAt(game,values);
                if(values[0]=="sub-library")response["blueprints"]=new ArrayList();
                return response;
            };
            NativeSubmarinePanel panel=new NativeSubmarinePanel(()=>new Dictionary<string,object>(shared),data=>{foreach(string key in new[]{"name","displacement","surface_speed"})shared[key]=data[key];},(close,order)=>{throw new Exception("Layout tests cannot save or order.");},message=>{},backend);
            panel.Dock=DockStyle.Fill;form.Controls.Add(panel);
            System.Windows.Forms.Timer poll=new System.Windows.Forms.Timer {Interval=100};int attempts=0;
            poll.Tick+=delegate{if(++attempts>200){Environment.ExitCode=1;form.Close();}else panel.PollShared();};
            bool done=false;
            panel.Evaluated+=delegate(Dictionary<string,object> result){
                if(done)return;done=true;poll.Stop();
                form.BeginInvoke((Action)delegate{try {
                    if(panel.FieldCount!=12)throw new Exception("The subsystem component did not expose its twelve non-shared fields.");
                    for(int page=0;page<3;page++) {panel.ShowPage(page);form.PerformLayout();if(panel.VisiblePageCount!=1)throw new Exception("The native-tab content switch must show exactly one page.");using(Bitmap capture=new Bitmap(form.Width,form.Height)){form.DrawToBitmap(capture,new Rectangle(Point.Empty,form.Size));capture.Save(Path.Combine(game,"Mods","Manager","native-submarine-panel-layout-"+page+".png"));}}
                    var report=new Dictionary<string,object>{{"ok",(bool)result["valid"]},{"scope","subsystem component layout only"},{"native_game_screen_verified",false},{"personal_saves_modified",false},{"library_writes",false},{"pages_rendered",3},{"field_count",panel.FieldCount},{"one_page_visible_at_a_time",true}};
                    File.WriteAllText(Path.Combine(game,"Mods","Manager","native-designer-layout-test.json"),new JavaScriptSerializer().Serialize(report));
                }catch(Exception e){File.WriteAllText(Path.Combine(game,"Mods","Manager","native-designer-layout-test.json"),new JavaScriptSerializer().Serialize(new{ok=false,error=e.ToString()}));Environment.ExitCode=1;}
                form.Close();});
            };
            form.Shown+=delegate{panel.Initialize();poll.Start();};Application.Run(form);
        }
    }
}
