using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Web.Script.Serialization;

internal static class BackendClient
{
    private static string Quote(string value)
    {
        if(value==null)value="";
        StringBuilder result=new StringBuilder("\"");int slashes=0;
        foreach(char c in value) {
            if(c=='\\') { slashes++;continue; }
            if(c=='\"') { result.Append('\\',slashes*2+1);result.Append(c);slashes=0;continue; }
            result.Append('\\',slashes);slashes=0;result.Append(c);
        }
        result.Append('\\',slashes*2);result.Append('"');return result.ToString();
    }

    internal static Task<Dictionary<string,object>> CallAt(string game,params string[] args)
    {
        return Task.Run(delegate {
            JavaScriptSerializer json=new JavaScriptSerializer { MaxJsonLength=16*1024*1024 };
            string python=Environment.GetEnvironmentVariable("RTW3_PYTHON");if(String.IsNullOrWhiteSpace(python))python="python.exe";
            ProcessStartInfo start=new ProcessStartInfo(python,Quote(Path.Combine(game,"Mods","Manager","mod_loader.py"))+" "+String.Join(" ",args.Select(Quote)));
            start.WorkingDirectory=game;start.UseShellExecute=false;start.CreateNoWindow=true;start.RedirectStandardOutput=true;start.RedirectStandardError=true;
            start.StandardOutputEncoding=Encoding.UTF8;start.StandardErrorEncoding=Encoding.UTF8;
            using(Process process=Process.Start(start)) {
                Task<string> output=process.StandardOutput.ReadToEndAsync(),errors=process.StandardError.ReadToEndAsync();
                if(!process.WaitForExit(150000))throw new Exception("The mod operation has not finished. Check the game and refresh before retrying.");
                string raw=output.Result.Trim();if(raw.Length==0)throw new Exception(errors.Result.Trim().Length>0?errors.Result.Trim():"The mod backend returned no response.");
                Dictionary<string,object> response=json.Deserialize<Dictionary<string,object>>(raw);
                if(!response.ContainsKey("ok") || !(bool)response["ok"])throw new Exception(response.ContainsKey("message")?response["message"].ToString():"The mod backend stopped.");
                return response;
            }
        });
    }
}
