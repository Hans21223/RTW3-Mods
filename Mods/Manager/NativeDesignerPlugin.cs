using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

namespace RTW3.Mods
{
    public static class NativeSubmarineEntry
    {
        private static int started;
        public static int Load(string configuration)
        {
            if(Interlocked.Exchange(ref started,1)!=0)return 2;
            try {
                var config=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(File.ReadAllText(configuration));
                using(Process self=Process.GetCurrentProcess()) {
                    if(self.Id!=Convert.ToInt32(config["pid"])||IntPtr.Size!=4||unchecked((uint)self.MainModule.BaseAddress.ToInt32())!=Convert.ToUInt32(config["base"])||
                       !String.Equals(self.MainModule.FileName,Path.Combine(config["game"].ToString(),"RTW3.exe"),StringComparison.OrdinalIgnoreCase))return 3;
                }
                Thread thread=new Thread(delegate(){try{Application.Run(new NativeDesignerHost(config));}catch(Exception e){config["error"]=e.ToString();config["ready"]=false;File.WriteAllText(config["report"].ToString(),new JavaScriptSerializer().Serialize(config));}});
                thread.IsBackground=true;thread.Name="RTW3 native ship-designer extension";thread.SetApartmentState(ApartmentState.STA);thread.Start();return 0;
            }catch{return 1;}
        }
    }

    internal sealed class NativeDesignerHost : Form
    {
        [DllImport("user32.dll")] private static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr window,out uint pid);
        [DllImport("user32.dll")] private static extern bool RegisterHotKey(IntPtr window,int id,uint modifiers,uint key);
        [DllImport("user32.dll")] private static extern bool UnregisterHotKey(IntPtr window,int id);
        [DllImport("user32.dll")] private static extern bool PostMessage(IntPtr window,uint message,IntPtr wp,IntPtr lp);
        private readonly Dictionary<string,object> config;
        private readonly JavaScriptSerializer json=new JavaScriptSerializer();
        private readonly int pid,queue;
        private readonly string game;
        private readonly System.Windows.Forms.Timer timer;
        private readonly NativeShipDesignerScreen screen;
        private bool hotkey,opening,saving,ordering,autoActivate;

        internal NativeDesignerHost(Dictionary<string,object> state)
        {
            config=state;pid=Convert.ToInt32(config["pid"]);queue=NativeShipDesignerScreen.Ptr(config["queue"]).ToInt32();game=config["game"].ToString();
            ShowInTaskbar=false;Opacity=0;Width=Height=1;Left=Top=-30000;
            screen=new NativeShipDesignerScreen(this,config,SaveClass,Report);
            timer=new System.Windows.Forms.Timer {Interval=200};timer.Tick+=delegate{Tick();};
            Shown+=delegate{config["ready"]=true;config["ui_mode"]="extension of original TfrmDesignMain2";config["separate_designer_window"]=false;config["self_test_complete"]=Convert.ToBoolean(config["self_test"]);config["self_test_scope"]="module startup only; native screen interaction requires separate verification";WriteReport();timer.Start();};
            FormClosed+=delegate{timer.Stop();if(hotkey)UnregisterHotKey(Handle,110);};
        }
        private void WriteReport(){File.WriteAllText(config["report"].ToString(),json.Serialize(config));}
        private void Report(string value){if(InvokeRequired){BeginInvoke((Action)delegate{Report(value);});return;}config["status"]=value;WriteReport();}
        private void Tick()
        {
            try {
                uint foreground;GetWindowThreadProcessId(GetForegroundWindow(),out foreground);
                if(foreground==(uint)pid&&!hotkey)hotkey=RegisterHotKey(Handle,110,0x4000,0x7a);
                else if(foreground!=(uint)pid&&hotkey){UnregisterHotKey(Handle,110);hotkey=false;}
                if(screen.BindIfVisible(pid)) {
                    config["native_designer_hwnd"]=screen.Window.ToInt32();
                    if(autoActivate){autoActivate=false;screen.Activate();}
                    screen.Poll();config["submarine_mode_active"]=screen.Active;
                }
            }catch(Exception e){config["error"]=e.ToString();WriteReport();timer.Stop();}
        }
        protected override void WndProc(ref Message message)
        {
            if(message.Msg==0x312&&message.WParam.ToInt32()==110){uint foreground;GetWindowThreadProcessId(GetForegroundWindow(),out foreground);if(foreground==(uint)pid)OpenDesigner();return;}
            base.WndProc(ref message);
        }
        private async void OpenDesigner()
        {
            if(opening||ordering)return;
            try {
                if(screen.BindIfVisible(pid)){screen.Activate();return;}
                int root=Marshal.ReadInt32(NativeShipDesignerScreen.Ptr(config["main_slot"]));
                int player=root==0?0:Marshal.ReadInt32(new IntPtr(root+Convert.ToInt32(config["player_field"])));
                if(player==0)throw new Exception("Load a campaign first. Then use Design Ship and select SS - Submarine class, or press F11.");
                int pending=Marshal.ReadInt32(new IntPtr(queue+0x40));if(pending==1||pending==3)throw new Exception("The native Ship design command is already open or pending.");
                opening=true;autoActivate=true;
                Marshal.WriteInt32(new IntPtr(queue+0x44),root);Marshal.WriteInt32(new IntPtr(queue+0x48),player);Thread.MemoryBarrier();Marshal.WriteInt32(new IntPtr(queue+0x40),1);
                PostMessage(GetForegroundWindow(),0,IntPtr.Zero,IntPtr.Zero);
                while((pending=Marshal.ReadInt32(new IntPtr(queue+0x40)))==1||pending==3)await Task.Delay(200);
                if(pending==4)throw new Exception("The campaign changed before Ship design opened. No class or ship was created.");
            }catch(Exception e){autoActivate=false;MessageBox.Show(e.Message,"Submarine class");Report(e.Message);}finally{opening=false;}
        }
        private async void SaveClass(bool close,bool order)
        {
            if(saving||screen.Panel==null||screen.Panel.IsBusy)return;saving=true;
            bool saved=false;
            try {
                screen.SetBusy(true);
                if(!await screen.Panel.SaveAsync())return;
                saved=true;
                string id=screen.Panel.ClassId;int revision=screen.Panel.Revision;
                if(close)screen.CloseAfterSave();
                if(order){while(NativeShipDesignerScreen.IsWindowVisible(screen.Window))await Task.Delay(100);await OrderClass(id,revision);}
            }catch(Exception e){Report(e.Message);MessageBox.Show(e.Message,"Submarine class");}finally{if(!saved||!close)screen.SetBusy(false);saving=false;}
        }
        private async Task OrderClass(string id,int revision)
        {
            if(ordering)throw new Exception("A native submarine order is already pending.");
            var packet=await BackendClient.CallAt(game,"sub-live-prepare","--pid",pid.ToString(),"--blueprint-id",id,"--revision",revision.ToString());
            if(MessageBox.Show("Order class "+packet["class_name"]+"?\nChoose native role: "+packet["role"]+".\n\nOnly class labels, availability and accuracy change. Native costs, research gates and build times remain.","Submarine construction",MessageBoxButtons.OKCancel,MessageBoxIcon.Information)!=DialogResult.OK)return;
            int state=Marshal.ReadInt32(new IntPtr(queue));if(state==1||state==3)throw new Exception("Finish the existing submarine order first.");
            ordering=true;
            try {
                Marshal.WriteInt32(new IntPtr(queue+4),NativeShipDesignerScreen.Ptr(packet["packet"]).ToInt32());Thread.MemoryBarrier();Marshal.WriteInt32(new IntPtr(queue),1);PostMessage(GetForegroundWindow(),0,IntPtr.Zero,IntPtr.Zero);
                while((state=Marshal.ReadInt32(new IntPtr(queue)))==1||state==3)await Task.Delay(200);
                if(state==4)throw new Exception("The campaign changed before construction opened. No class was applied.");
                int count=unchecked(Marshal.ReadInt32(new IntPtr(queue+12))-Marshal.ReadInt32(new IntPtr(queue+8)));Report(count+" matching native submarine(s) created with this class profile. Save normally in RTW3.");
            }finally{ordering=false;}
        }
    }
}
