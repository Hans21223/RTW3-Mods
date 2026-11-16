using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;

namespace RTW3.Mods
{
    // Extends the original TfrmDesignMain2 HWND. No replacement top-level form.
    internal sealed class NativeShipDesignerScreen
    {
        [StructLayout(LayoutKind.Sequential)] internal struct Rect { internal int Left,Top,Right,Bottom; }
        [StructLayout(LayoutKind.Sequential,CharSet=CharSet.Unicode)] private struct TabItem { internal uint mask,state,stateMask;internal IntPtr text;internal int textMax,image;internal IntPtr param; }
        private delegate bool Enumerate(IntPtr window,IntPtr ignored);
        [UnmanagedFunctionPointer(CallingConvention.Winapi)] private delegate IntPtr WindowProc(IntPtr window,uint message,IntPtr wp,IntPtr lp);
        [DllImport("user32.dll")] private static extern bool EnumWindows(Enumerate callback,IntPtr ignored);
        [DllImport("user32.dll")] private static extern bool EnumChildWindows(IntPtr window,Enumerate callback,IntPtr ignored);
        [DllImport("user32.dll",CharSet=CharSet.Unicode)] private static extern int GetClassName(IntPtr window,StringBuilder text,int max);
        [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr window,out uint pid);
        [DllImport("user32.dll")] internal static extern bool IsWindowVisible(IntPtr window);
        [DllImport("user32.dll")] private static extern bool IsWindowEnabled(IntPtr window);
        [DllImport("user32.dll")] private static extern bool IsWindow(IntPtr window);
        [DllImport("user32.dll")] private static extern bool IsChild(IntPtr parent,IntPtr child);
        [DllImport("user32.dll")] private static extern bool GetWindowRect(IntPtr window,out Rect rect);
        [DllImport("user32.dll")] private static extern bool GetClientRect(IntPtr window,out Rect rect);
        [DllImport("user32.dll")] private static extern int MapWindowPoints(IntPtr from,IntPtr to,ref Rect rect,uint points);
        [DllImport("user32.dll")] internal static extern IntPtr SetParent(IntPtr child,IntPtr parent);
        [DllImport("user32.dll")] internal static extern bool MoveWindow(IntPtr window,int x,int y,int width,int height,bool repaint);
        [DllImport("user32.dll")] private static extern bool ShowWindow(IntPtr window,int how);
        [DllImport("user32.dll")] private static extern bool EnableWindow(IntPtr window,bool enable);
        [DllImport("user32.dll",CharSet=CharSet.Unicode)] private static extern IntPtr SendMessage(IntPtr window,uint message,IntPtr wp,IntPtr lp);
        [DllImport("user32.dll",CharSet=CharSet.Unicode,EntryPoint="SendMessageW")] private static extern IntPtr SendText(IntPtr window,uint message,IntPtr wp,string text);
        [DllImport("user32.dll",CharSet=CharSet.Unicode)] private static extern bool PostMessage(IntPtr window,uint message,IntPtr wp,IntPtr lp);
        [DllImport("user32.dll",CharSet=CharSet.Unicode)] private static extern uint RegisterWindowMessage(string message);
        [DllImport("user32.dll",EntryPoint="SetWindowLongW",SetLastError=true)] private static extern IntPtr SetWindowLong(IntPtr window,int index,IntPtr value);
        [DllImport("user32.dll")] private static extern IntPtr CallWindowProc(IntPtr previous,IntPtr window,uint message,IntPtr wp,IntPtr lp);
        [DllImport("kernel32.dll",SetLastError=true)] private static extern bool ReadProcessMemory(IntPtr process,IntPtr address,byte[] data,IntPtr size,out IntPtr actual);
        internal static IntPtr Ptr(object number) {return new IntPtr(unchecked((int)Convert.ToUInt32(number)));}
        private static byte[] Read(IntPtr at,int count) {byte[] data=new byte[count];IntPtr got;if(!ReadProcessMemory(new IntPtr(-1),at,data,new IntPtr(count),out got)||got.ToInt32()!=count)throw new Exception("Native designer changed while binding controls.");return data;}
        private static IntPtr Pointer(IntPtr at) {return new IntPtr(BitConverter.ToInt32(Read(at,4),0));}
        private static string Class(IntPtr window) {StringBuilder s=new StringBuilder(256);GetClassName(window,s,256);return s.ToString();}
        private static string Text(IntPtr window) {
            int count=SendMessage(window,14,IntPtr.Zero,IntPtr.Zero).ToInt32();if(count<0||count>10000)return "";
            IntPtr memory=Marshal.AllocHGlobal((count+1)*2);try {SendMessage(window,13,new IntPtr(count+1),memory);return Marshal.PtrToStringUni(memory)??"";}finally{Marshal.FreeHGlobal(memory);}
        }
        private static void SetText(IntPtr window,string value) {SendText(window,12,IntPtr.Zero,value);}
        private static int Selection(IntPtr window) {return SendMessage(window,0x147,IntPtr.Zero,IntPtr.Zero).ToInt32();}
        private static void Select(IntPtr window,int index) {SendMessage(window,0x14e,new IntPtr(index),IntPtr.Zero);}
        private readonly Control dispatcher;
        private readonly Dictionary<string,object> layout;
        private readonly Dictionary<string,IntPtr> controls=new Dictionary<string,IntPtr>();
        private readonly Dictionary<IntPtr,bool> enabled=new Dictionary<IntPtr,bool>(),visible=new Dictionary<IntPtr,bool>();
        private readonly Dictionary<IntPtr,string> texts=new Dictionary<IntPtr,string>();
        private readonly WindowProc callback;
        private IntPtr previous,formObject;
        private readonly IntPtr state;
        private readonly uint actionMessage;
        private byte originalEditing;
        private int originalType,subIndex=-1;
        private string originalTitle;
        private string[] oldTabs;
        private bool altering;
        internal bool Active {get;private set;}
        internal IntPtr Window {get;private set;}
        internal NativeSubmarinePanel Panel {get;private set;}
        private PictureBox viewport;
        private Label summary;
        private readonly Action<bool,bool> save;
        private readonly Action<string> report;
        private Dictionary<string,object> pendingShared;
        private readonly object sync=new object();
        private bool wasVisible;
        private int lastSurfaceType;
        private readonly Func<string[],System.Threading.Tasks.Task<Dictionary<string,object>>> backend;

        internal NativeShipDesignerScreen(Control owner,Dictionary<string,object> config,Action<bool,bool> saveClass,Action<string> status)
        {
            dispatcher=owner;layout=(Dictionary<string,object>)config["native_designer"];state=Ptr(layout["state"]);save=saveClass;report=status;
            backend=args=>BackendClient.CallAt(config["game"].ToString(),args);
            callback=WndProc;actionMessage=RegisterWindowMessage("RTW3.NativeSubmarineDesigner."+config["nonce"]);
        }

        internal bool BindIfVisible(int pid)
        {
            if(Window!=IntPtr.Zero && IsWindow(Window)) {
                bool current=IsWindowVisible(Window);
                if(current&&!wasVisible)EnsureTypeEntry();
                if(!current&&Active)PostMessage(Window,actionMessage,new IntPtr(2),IntPtr.Zero);
                wasVisible=current;return current;
            }
            IntPtr found=IntPtr.Zero;
            EnumWindows(delegate(IntPtr w,IntPtr ignored) {uint p;GetWindowThreadProcessId(w,out p);if(p==(uint)pid&&IsWindowVisible(w)&&Class(w)=="TfrmDesignMain2")found=w;return true;},IntPtr.Zero);
            if(found==IntPtr.Zero)return false;
            if(Panel!=null){Panel.Dispose();Panel=null;}
            if(viewport!=null){viewport.Dispose();viewport=null;}
            if(summary!=null){summary.Dispose();summary=null;}
            controls.Clear();
            IntPtr instance=Pointer(Ptr(layout["slot"]));if(Pointer(instance)!=Ptr(layout["vmt"]))throw new Exception("The original designer class changed.");
            HashSet<IntPtr> children=new HashSet<IntPtr>();EnumChildWindows(found,delegate(IntPtr w,IntPtr p){children.Add(w);return true;},IntPtr.Zero);
            Dictionary<string,object> fields=(Dictionary<string,object>)layout["fields"];
            foreach(string name in new[] {"cbType","edName","seDisplacement","seSpeed","tcArmament","pnGuns","pnAdditional","pnGraphics","Panel2","Globe41","btbnFinish","stHull","stMachineryWeight","stSumAll","stWeightResult","stTotalCost","stTime","stMonthlyCost","stMachineryCost","stArmamentWeight","stArmamentCost","stHullCost"}) {
                IntPtr obj=Pointer(new IntPtr(instance.ToInt32()+Convert.ToInt32(fields[name])));IntPtr vmt=Pointer(obj);
                int size=BitConverter.ToInt32(Read(new IntPtr(vmt.ToInt32()-52),4),0);
                if(size<16||size>0x10000)throw new Exception("Unsupported native control instance size.");
                byte[] bytes=Read(obj,Math.Min(size,0x400));HashSet<IntPtr> matches=new HashSet<IntPtr>();
                for(int off=4;off+4<=bytes.Length;off+=4) {IntPtr candidate=new IntPtr(BitConverter.ToInt32(bytes,off));if(children.Contains(candidate))matches.Add(candidate);}
                if(matches.Count==1)controls[name]=matches.First();
            }
            foreach(string key in new[] {"cbType","edName","seDisplacement","seSpeed","tcArmament","Panel2","btbnFinish"})if(!controls.ContainsKey(key))throw new Exception("Cannot verify native control handle: "+key);
            Window=found;formObject=instance;wasVisible=true;
            previous=SetWindowLong(Window,-4,Marshal.GetFunctionPointerForDelegate(callback));if(previous==IntPtr.Zero)throw new Exception("Cannot extend the native designer message handler.");
            EnsureTypeEntry();
            report("Native Ship design controls bound. Choose SS - Submarine class in Ship type.");return true;
        }

        private void EnsureTypeEntry()
        {
            int current=Selection(controls["cbType"]);
            subIndex=SendText(controls["cbType"],0x158,new IntPtr(-1),"SS - Submarine class").ToInt32();
            if(subIndex<0)subIndex=SendText(controls["cbType"],0x143,IntPtr.Zero,"SS - Submarine class").ToInt32();
            if(subIndex<0)throw new Exception("Could not add the submarine mode to Ship type.");
            if(current>=0&&current!=subIndex)lastSurfaceType=current;
        }

        internal void Activate() {if(Window!=IntPtr.Zero)PostMessage(Window,actionMessage,new IntPtr(1),IntPtr.Zero);}
        internal void CloseAfterSave() {PostMessage(Window,actionMessage,new IntPtr(3),IntPtr.Zero);}
        internal void SetBusy(bool value) {if(Window!=IntPtr.Zero)SendMessage(Window,actionMessage,new IntPtr(value?5:6),IntPtr.Zero);}
        internal void ApplyShared(Dictionary<string,object> design) {lock(sync)pendingShared=design;PostMessage(Window,actionMessage,new IntPtr(4),IntPtr.Zero);}
        internal Dictionary<string,object> Shared()
        {
            int tons,speed;if(!Int32.TryParse(Text(controls["seDisplacement"]),out tons)||!Int32.TryParse(Text(controls["seSpeed"]),out speed))throw new Exception("Enter whole-number displacement and speed in the native designer.");
            return new Dictionary<string,object>{{"name",Text(controls["edName"])},{"displacement",tons},{"surface_speed",speed}};
        }

        private IntPtr WndProc(IntPtr w,uint message,IntPtr wp,IntPtr lp)
        {
            try {
                if(message==actionMessage) {
                    if(wp.ToInt32()==1)Enter();
                    else if(wp.ToInt32()==2)Leave();
                    else if(wp.ToInt32()==3) {Leave();PostMessage(Window,16,IntPtr.Zero,IntPtr.Zero);}
                    else if(wp.ToInt32()==4 && Active) {
                        Dictionary<string,object> data;lock(sync){data=pendingShared;pendingShared=null;}
                        if(data!=null) {SetText(controls["edName"],data["name"].ToString());SetText(controls["seDisplacement"],data["displacement"].ToString());SetText(controls["seSpeed"],data["surface_speed"].ToString());}
                    }
                    else if((wp.ToInt32()==5||wp.ToInt32()==6)&&Active)foreach(string key in new[]{"cbType","edName","seDisplacement","seSpeed","tcArmament","btbnFinish"})EnableWindow(controls[key],wp.ToInt32()==6);
                    return IntPtr.Zero;
                }
                if(message==0x111 && lp==controls["cbType"] && ((wp.ToInt32()>>16)&0xffff)==1) {
                    int chosen=Selection(controls["cbType"]);
                    if(subIndex>=0&&chosen==subIndex) {Enter();return IntPtr.Zero;}
                    if(Active) {if(Panel!=null&&!Panel.CanDiscard()){Select(controls["cbType"],subIndex);return IntPtr.Zero;}Leave();Select(controls["cbType"],chosen);}
                    lastSurfaceType=chosen;
                }
                if(message==16 && Active) {
                    if(Panel!=null && (Panel.IsBusy || !Panel.CanDiscard()))return IntPtr.Zero;
                    Leave();
                }
                if(message==0x82) {Leave();Window=IntPtr.Zero;}
            } catch(Exception e) {
                report(e.Message);
                if((message==actionMessage&&wp.ToInt32()==1) || (message==0x111&&lp==controls["cbType"])) {
                    if(Active)Leave();else Select(controls["cbType"],lastSurfaceType);
                }
                // Fail closed for an unsupported SS selection: never feed it
                // into the native surface-type converter or surface save path.
                if(message==actionMessage || Active || (message==0x111&&lp==controls["cbType"]))return IntPtr.Zero;
            }
            return CallWindowProc(previous,w,message,wp,lp);
        }

        private void Enter()
        {
            if(Active||altering)return;altering=true;
            try {
                originalType=lastSurfaceType;
                originalTitle=Text(Window);originalEditing=Read(new IntPtr(formObject.ToInt32()+Convert.ToInt32(layout["editing_field"])),1)[0];
                enabled.Clear();visible.Clear();texts.Clear();
                EnumChildWindows(Window,delegate(IntPtr child,IntPtr ignored){if(Panel!=null&&(child==Panel.Handle||IsChild(Panel.Handle,child)))return true;if(viewport!=null&&child==viewport.Handle)return true;if(summary!=null&&child==summary.Handle)return true;enabled[child]=IsWindowEnabled(child);visible[child]=IsWindowVisible(child);return true;},IntPtr.Zero);
                foreach(IntPtr control in controls.Values.Distinct())texts[control]=Text(control);
                oldTabs=Enumerable.Range(0,3).Select(GetTab).ToArray();
                Marshal.WriteInt32(new IntPtr(state.ToInt32()+4),formObject.ToInt32());Marshal.WriteInt32(state,1);
                Marshal.WriteByte(new IntPtr(formObject.ToInt32()+Convert.ToInt32(layout["editing_field"])),0);
                Active=true;Select(controls["cbType"],subIndex);
                foreach(IntPtr child in enabled.Keys)EnableWindow(child,false);
                foreach(string key in new[]{"cbType","edName","seDisplacement","seSpeed","tcArmament","btbnFinish"})EnableWindow(controls[key],true);
                foreach(string key in new[]{"seDisplacement","seSpeed"})EnumChildWindows(controls[key],delegate(IntPtr child,IntPtr ignored){EnableWindow(child,true);return true;},IntPtr.Zero);
                foreach(string key in new[]{"pnGuns","pnAdditional","pnGraphics"})if(controls.ContainsKey(key))ShowWindow(controls[key],0);
                SetText(Window,originalTitle+" - Submarine class (experimental)");
                SetTab(0,"Machinery / hull");SetTab(1,"Armament / sensors");SetTab(2,"Submarine classes");
                foreach(string key in new[]{"stTotalCost","stTime","stMonthlyCost","stMachineryCost","stArmamentCost","stHullCost"})if(controls.ContainsKey(key))SetText(controls[key],"---");
                dispatcher.BeginInvoke((Action)delegate {
                    if(!Active)return;
                    if(Panel==null) {Panel=new NativeSubmarinePanel(Shared,ApplyShared,save,report,backend);Panel.Evaluated+=SetWeights;Panel.CreateControl();SetParent(Panel.Handle,Window);}
                    if(viewport==null) {viewport=new PictureBox {BackColor=Color.FromArgb(204,255,255)};viewport.Paint+=delegate(object s,PaintEventArgs e){if(Panel!=null)Panel.DrawHull(e.Graphics,viewport.ClientRectangle);};IntPtr h=viewport.Handle;SetParent(h,Window);}
                    if(summary==null){summary=new Label {BackColor=Color.FromArgb(51,51,51),ForeColor=Color.Silver,Font=new Font("Tahoma",8.25F),Padding=new Padding(7,10,7,7),UseMnemonic=false,Text="SUBMARINE CLASS\n\nLoading layout weights...\n\nNative submarine cost and construction rules remain unchanged."};IntPtr h=summary.Handle;SetParent(h,Window);}
                    Layout();ShowWindow(Panel.Handle,5);ShowWindow(viewport.Handle,5);ShowWindow(summary.Handle,5);Panel.Initialize();
                });
            } finally {altering=false;}
        }

        internal void Poll()
        {
            if(!Active)return;
            Layout();if(Panel!=null){Panel.PollShared();Panel.ShowPage(SendMessage(controls["tcArmament"],0x130b,IntPtr.Zero,IntPtr.Zero).ToInt32());}
            int signal=Marshal.ReadInt32(new IntPtr(state.ToInt32()+8));if(signal!=0){Marshal.WriteInt32(new IntPtr(state.ToInt32()+8),0);if(signal==3&&Panel!=null)Panel.RequestEvaluation();else if(signal==4){SendMessage(controls["tcArmament"],0x130c,new IntPtr(2),IntPtr.Zero);if(Panel!=null)Panel.ShowPage(2);}else if(signal==1||signal==2)save(signal==1,false);}
            if(viewport!=null)viewport.Invalidate();
        }
        internal void SetWeights(Dictionary<string,object> result)
        {
            if(!Active)return;
            var allocation=(Dictionary<string,object>)result["allocation"];
            if(summary!=null){StringBuilder lines=new StringBuilder("SUBMARINE CLASS - ESTIMATED WEIGHTS\n\n");foreach(var row in allocation){lines.AppendLine(row.Key);lines.AppendLine("    "+row.Value+" tons\n");}lines.AppendLine("Total allocated: "+result["used_tons"]+" tons");lines.AppendLine("Weight remaining: "+result["margin_tons"]+" tons\n");lines.AppendLine("Native costs and build times remain role/research based.\nThe surface-ship yard selection does not set submarine costs.");summary.Text=lines.ToString();}
            foreach(var row in new[]{new[]{"stHull","Hull and pressure structure"},new[]{"stMachineryWeight","Propulsion"}})if(controls.ContainsKey(row[0]))SetText(controls[row[0]],allocation[row[1]].ToString());
            foreach(var row in new[]{new[]{"stSumAll","used_tons"},new[]{"stWeightResult","margin_tons"}})if(controls.ContainsKey(row[0]))SetText(controls[row[0]],result[row[1]].ToString());
        }
        private void Layout()
        {
            if(Panel!=null){Rect r;GetWindowRect(controls["tcArmament"],out r);MapWindowPoints(IntPtr.Zero,Window,ref r,2);MoveWindow(Panel.Handle,r.Left+3,r.Top+25,r.Right-r.Left-6,r.Bottom-r.Top-28,true);}
            if(viewport!=null){Rect r;GetWindowRect(controls["Panel2"],out r);MapWindowPoints(IntPtr.Zero,Window,ref r,2);MoveWindow(viewport.Handle,r.Left+2,r.Top+2,r.Right-r.Left-4,r.Bottom-r.Top-4,true);}
            if(summary!=null){Rect s,c,t,f;GetWindowRect(controls["seSpeed"],out s);GetWindowRect(controls["edName"],out c);GetWindowRect(controls["tcArmament"],out t);GetWindowRect(controls["btbnFinish"],out f);MapWindowPoints(IntPtr.Zero,Window,ref s,2);MapWindowPoints(IntPtr.Zero,Window,ref c,2);MapWindowPoints(IntPtr.Zero,Window,ref t,2);MapWindowPoints(IntPtr.Zero,Window,ref f,2);int left=c.Left-(int)((c.Right-c.Left)*0.42);MoveWindow(summary.Handle,left,s.Bottom+20,t.Left-left-10,f.Bottom-s.Bottom-20,true);}
        }
        private string GetTab(int index) {IntPtr buf=Marshal.AllocHGlobal(512);Marshal.Copy(new byte[512],0,buf,512);try{TabItem item=new TabItem {mask=1,text=buf,textMax=256};IntPtr mem=Marshal.AllocHGlobal(Marshal.SizeOf(item));try{Marshal.StructureToPtr(item,mem,false);if(SendMessage(controls["tcArmament"],0x133c,new IntPtr(index),mem)==IntPtr.Zero)throw new Exception("Cannot read the original armament tabs.");return (Marshal.PtrToStringUni(buf,256)??"").Split('\0')[0];}finally{Marshal.FreeHGlobal(mem);}}finally{Marshal.FreeHGlobal(buf);}}
        private void SetTab(int index,string text) {IntPtr buf=Marshal.StringToHGlobalUni(text);TabItem item=new TabItem {mask=1,text=buf};IntPtr mem=Marshal.AllocHGlobal(Marshal.SizeOf(item));try{Marshal.StructureToPtr(item,mem,false);SendMessage(controls["tcArmament"],0x133d,new IntPtr(index),mem);}finally{Marshal.FreeHGlobal(mem);Marshal.FreeHGlobal(buf);}}

        private void Leave()
        {
            if(!Active||altering)return;altering=true;
            try {
                Marshal.WriteByte(new IntPtr(formObject.ToInt32()+Convert.ToInt32(layout["editing_field"])),0);
                if(Panel!=null)ShowWindow(Panel.Handle,0);if(viewport!=null)ShowWindow(viewport.Handle,0);if(summary!=null)ShowWindow(summary.Handle,0);
                foreach(var pair in texts)if(IsWindow(pair.Key))SetText(pair.Key,pair.Value);
                for(int i=0;i<3;i++)SetTab(i,oldTabs[i]);Select(controls["cbType"],originalType);
                foreach(var pair in visible)if(IsWindow(pair.Key))ShowWindow(pair.Key,pair.Value?5:0);
                foreach(var pair in enabled)if(IsWindow(pair.Key))EnableWindow(pair.Key,pair.Value);
                SetText(Window,originalTitle);
                Marshal.WriteByte(new IntPtr(formObject.ToInt32()+Convert.ToInt32(layout["editing_field"])),originalEditing);
                Marshal.WriteInt32(state,0);Marshal.WriteInt32(new IntPtr(state.ToInt32()+8),0);Active=false;
            } finally {altering=false;}
        }
    }
}
