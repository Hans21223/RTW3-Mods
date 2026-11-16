"""Experimental submarine blueprint designer and backed-up native save bridge.

The component model is a game-balance estimate, not naval architecture. Native
integration is deliberately limited to verified existing submarine fields.
"""
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import uuid
import save_cheats as saves

HERE=Path(__file__).resolve().parent
LIBRARY=HERE/"submarine-blueprints.json"
ROLES={"medium":0,"minelayer":1,"coastal":2,"long-range":3,"missile":4}
PROPULSION={"diesel-electric":1901,"aip":1980,"nuclear":1955}
NUMBERS={"year":(1901,2030),"displacement":(100,50000),"surface_speed":(4,40),
         "submerged_speed":(3,45),"depth":(30,800),"torpedo_tubes":(0,12),
         "torpedo_load":(0,100),"missile_cells":(0,48),"sonar":(0,3),
         "quieting":(0,3),"reliability":(0,3),"battery":(1,4)}
DEFAULT={"name":"Patrol I","year":1935,"role":"medium","propulsion":"diesel-electric",
         "displacement":1500,"surface_speed":18,"submerged_speed":9,"depth":150,
         "torpedo_tubes":6,"torpedo_load":18,"missile_cells":0,"sonar":1,
         "quieting":1,"reliability":2,"battery":2}
TEMPLATES=[
    {**DEFAULT,"name":"Coastal Scout","year":1910,"role":"coastal","displacement":450,
     "surface_speed":12,"submerged_speed":7,"depth":60,"torpedo_tubes":2,"torpedo_load":6,
     "sonar":0,"quieting":0,"battery":1},
    DEFAULT,
    {**DEFAULT,"name":"Ocean Hunter","year":1960,"role":"long-range","propulsion":"nuclear",
     "displacement":5500,"surface_speed":18,"submerged_speed":28,"depth":350,
     "torpedo_tubes":6,"torpedo_load":28,"sonar":2,"quieting":2,"reliability":2,"battery":1},
    {**DEFAULT,"name":"Quiet Patrol","year":2000,"role":"medium","propulsion":"aip",
     "displacement":2300,"surface_speed":14,"submerged_speed":20,"depth":300,
     "torpedo_tubes":6,"torpedo_load":20,"sonar":3,"quieting":3,"battery":4},
    {**DEFAULT,"name":"Missile Hunter","year":2020,"role":"missile","propulsion":"nuclear",
     "displacement":9500,"surface_speed":20,"submerged_speed":30,"depth":450,
     "torpedo_tubes":6,"torpedo_load":32,"missile_cells":24,"sonar":3,"quieting":3,"battery":1}
]


def text(value,label,maximum=80):
    if not isinstance(value,str) or not value.strip() or len(value)>maximum or any(ord(c)<32 for c in value):
        raise ValueError("Enter a single-line "+label+" (1-"+str(maximum)+" characters).")
    return value.strip()


def evaluate(values):
    if not isinstance(values,dict) or set(values)-set(DEFAULT): raise ValueError("Unsupported blueprint fields.")
    if set(DEFAULT)-set(values): raise ValueError("Blueprint is missing required components.")
    design=dict(values); design["name"]=text(design["name"],"class name")
    for key,(low,high) in NUMBERS.items():
        number=design[key]
        if isinstance(number,bool) or not isinstance(number,int) or not low<=number<=high:
            raise ValueError(f"{key} must be an integer from {low} to {high}.")
    if design["role"] not in ROLES or design["propulsion"] not in PROPULSION:
        raise ValueError("Choose a supported role and propulsion.")
    if design["year"]<PROPULSION[design["propulsion"]]:
        raise ValueError("This propulsion is earlier than the mod's availability year.")
    if design["missile_cells"] and (design["year"]<1956 or design["role"]!="missile"):
        raise ValueError("Missile cells require the missile role and a design year of 1956 or later.")
    if design["role"]=="missile" and not design["missile_cells"]:
        raise ValueError("Missile submarines need at least one missile cell.")
    if not design["torpedo_tubes"] or design["torpedo_load"]<design["torpedo_tubes"]:
        raise ValueError("Provide torpedo tubes and at least one torpedo per tube.")
    if design["propulsion"]=="nuclear" and design["displacement"]<2500:
        raise ValueError("The mod's reactor layout needs at least 2,500 tons.")
    # Explicitly a lightweight allocation model. These tonnages are NOT written
    # over the engine's fixed submarine-type tonnage tables.
    tons=design["displacement"]
    hull=round(tons*(0.43+design["depth"]/7000))
    propulsion_base={"diesel-electric":35,"aip":100,"nuclear":850}[design["propulsion"]]
    propulsion=round(propulsion_base+tons*(design["submerged_speed"]/45)**3*0.32
                     +tons*(design["surface_speed"]/40)**3*0.08)
    battery=round(tons*design["battery"]*0.035) if design["propulsion"]!="nuclear" else round(tons*0.025)
    weapons=round(design["torpedo_tubes"]*8+design["torpedo_load"]*2+design["missile_cells"]*18)
    systems=round(tons*0.10+design["sonar"]*12+design["quieting"]*tons*0.018+design["reliability"]*8)
    allocations={"Hull and pressure structure":hull,"Propulsion":propulsion,"Batteries / auxiliaries":battery,
                 "Weapons":weapons,"Sensors, accommodation and margins":systems}
    used=sum(allocations.values()); margin=tons-used
    complexity=(3 if design["propulsion"]=="nuclear" else 1 if design["propulsion"]=="aip" else 0)+design["missile_cells"]//12
    availability=max(40,min(130,58+design["reliability"]*12+design["quieting"]*3-complexity*3))
    accuracy=max(-2,min(1,design["sonar"]-2))
    build_turns=min(120,max(8,math.ceil(10+tons/600+design["missile_cells"]/4+complexity*2)))
    warnings=["Projected size, speed, depth and equipment are blueprint specifications only; native tonnage, weapon counts, costs and tactical movement are not changed.",
              "The native bridge applies availability, accuracy and optional remaining construction turns only. Native research, roles and operating-area rules remain.",
              "This allocation and performance model is a mod estimate, not a validated real-ship design calculation."]
    if design["year"]>1970: warnings.append("Post-1970 blueprints require an extended campaign; no new modern research is added by this designer.")
    if margin<0: warnings.insert(0,"Over allocation by "+str(-margin)+" tons. Reduce equipment or increase displacement before saving/applying.")
    return {"ok":True,"design":design,"valid":margin>=0,"allocation":allocations,"used_tons":used,"margin_tons":margin,
            "native":{"availability":availability,"accuracy":accuracy,"suggested_build_turns":build_turns,"type":ROLES[design["role"]]},
            "warnings":warnings,"tactical_control_implemented":False,"modern_weapons_implemented":False}


def empty_library(): return {"schema":1,"blueprints":{}}


def read_library():
    if not LIBRARY.exists(): return empty_library()
    data=json.loads(LIBRARY.read_text(encoding="utf-8"))
    if data.get("schema")!=1 or not isinstance(data.get("blueprints"),dict): raise ValueError("Unsupported blueprint library. Preserve the file and inspect it.")
    return data


def atomic_json(path,data):
    temporary=path.with_name(path.name+".submarine-tmp")
    if temporary.exists(): raise ValueError("A previous submarine transaction needs inspection: "+str(temporary))
    try:
        with temporary.open("x",encoding="utf-8",newline="\n") as stream: json.dump(data,stream,indent=2,ensure_ascii=False);stream.write("\n")
        if json.loads(temporary.read_text(encoding="utf-8"))!=data: raise ValueError("Blueprint verification failed.")
        temporary.replace(path)
    finally: temporary.unlink(missing_ok=True)


def library():
    data=read_library()
    return {"ok":True,"blueprints":[{"id":key,**value} for key,value in data["blueprints"].items()],
            "templates":TEMPLATES,"roles":list(ROLES),"propulsion":list(PROPULSION),"bounds":NUMBERS,
            "capabilities":{"blueprints":True,"native_saved_stats":True,"tactical_control":False,"custom_native_tonnage":False,"modern_weapons":False}}


def save_blueprint(values,ident=None,expected_revision=None):
    result=evaluate(values)
    if not result["valid"]: raise ValueError("Blueprint is over its displacement allocation.")
    data=read_library()
    if ident:
        if ident not in data["blueprints"]: raise ValueError("Blueprint no longer exists. Refresh the library.")
        if data["blueprints"][ident]["revision"]!=expected_revision: raise ValueError("Blueprint changed. Reload it before saving.")
        revision=expected_revision+1
    else:
        ident=uuid.uuid4().hex;revision=1
    data["blueprints"][ident]={"revision":revision,"design":result["design"],"updated":dt.datetime.now().isoformat(timespec="seconds")}
    # Retain a recoverable copy of an existing library before editing a class.
    if LIBRARY.exists():
        backup=HERE/"submarine-library-backups";backup.mkdir(exist_ok=True)
        shutil.copy2(LIBRARY,backup/(dt.datetime.now().strftime("%Y%m%d-%H%M%S")+"-"+uuid.uuid4().hex[:8]+".json"))
    atomic_json(LIBRARY,data)
    return {"ok":True,"id":ident,"revision":revision,"evaluation":result,"message":"Blueprint saved. Native campaign values are unchanged until you explicitly apply it."}


def inspect_save(value,nation="Nation0"):
    import mod_loader
    path=saves.resolve_save(value);raw=path.read_bytes();_,sections,_=saves.parse(raw)
    if not re.fullmatch(r"Nation\d+",nation) or nation not in sections: raise ValueError("Choose an existing nation.")
    data=sections.get(nation+"Submarines",{})
    count=int(data.get("SubCount",0))
    if not 0<=count<=10000: raise ValueError("Unsupported submarine count.")
    rows=[]
    for index in range(count):
        prefix="Sub"+str(index)
        if data.get(prefix+"Sunk")!="0" or data.get(prefix+"InPlay")!="1": continue
        try:
            role=int(data[prefix+"SubType"])
            if role not in ROLES.values(): continue
            rows.append({"index":index,"name":data[prefix+"Name"],"role":next(k for k,v in ROLES.items() if v==role),
                         "availability":int(data[prefix+"Availability"]),"accuracy":int(data[prefix+"Accuracy"]),
                         "remaining_turns":int(data[prefix+"RemainingBuildTime"]),"year_built":int(data[prefix+"YearBuilt"])})
        except (KeyError,ValueError): continue
    bindings=path.with_name(path.stem+".submarine-designs.json")
    linked=json.loads(bindings.read_text(encoding="utf-8")) if bindings.exists() else {"schema":1,"bindings":{}}
    if linked.get("schema")!=1 or not isinstance(linked.get("bindings"),dict): raise ValueError("Unsupported submarine binding file.")
    return {"ok":True,"path":str(path),"sha256":hashlib.sha256(raw).hexdigest(),"nation":nation,
            "year":int(sections["General"]["Year"]),"boats":rows,
            "nations":[{"id":key,"name":data.get("Name",key)} for key,data in sections.items() if re.fullmatch(r"Nation\d+",key)],
            "bindings":linked["bindings"],"game_running":bool(mod_loader.running_games())}


def apply_blueprint(value,nation,index,ident,revision,expected_hash,adjust_build=False):
    import mod_loader
    if mod_loader.running_games(): raise ValueError("Save and close RTW3 before applying a submarine blueprint.")
    if isinstance(index,bool) or not isinstance(index,int) or not 0<=index<10000:
        raise ValueError("Choose a valid submarine index.")
    path=saves.resolve_save(value)
    before=inspect_save(path,nation)
    if not expected_hash or before["sha256"]!=expected_hash: raise ValueError("The save changed. Reload submarines before applying.")
    stored=read_library()["blueprints"].get(ident)
    if not stored or stored["revision"]!=revision: raise ValueError("Blueprint changed. Reload it before applying.")
    result=evaluate(stored["design"])
    if not result["valid"]: raise ValueError("Blueprint is over allocation.")
    boat=next((r for r in before["boats"] if r["index"]==index),None)
    if boat is None: raise ValueError("Choose an existing, unsunk submarine.")
    if boat["role"]!=result["design"]["role"]: raise ValueError("Blueprint and boat must have the same native role. The designer does not change boat identity or unlock roles.")
    if before["year"]<result["design"]["year"]: raise ValueError("Blueprint design year is later than this campaign.")
    if adjust_build and boat["remaining_turns"]<=0: raise ValueError("Only a submarine under construction can have its build time adjusted.")
    prefix="Sub"+str(index); owner=nation+"Submarines"
    fields={(owner,prefix+"Availability"):result["native"]["availability"],(owner,prefix+"Accuracy"):result["native"]["accuracy"]}
    if adjust_build: fields[owner,prefix+"RemainingBuildTime"]=result["native"]["suggested_build_turns"]
    raw=path.read_bytes();output=saves.replace_fields(raw,fields)
    binding_path=path.with_name(path.stem+".submarine-designs.json")
    binding_raw=binding_path.read_bytes() if binding_path.exists() else None
    bindings=json.loads(binding_raw) if binding_raw is not None else {"schema":1,"bindings":{}}
    key=nation+"/"+str(index)
    bindings["bindings"][key]={"boat_name":boat["name"],"year_built":boat["year_built"],"native_role":boat["role"],
                              "blueprint_id":ident,"revision":revision,"design":result["design"],"native":result["native"],
                              "applied":dt.datetime.now().isoformat(timespec="seconds")}
    # Prepare and verify the sidecar before touching the campaign. The full-slot
    # backup includes any prior sidecar. A journal in that backup describes both
    # files; a failed second replacement restores the native save when unchanged.
    # Same volume as the slot, but outside it so the slot backup does not capture
    # our in-progress temporary file. Never use the D: manager folder for a C:
    # save-file rename.
    temporary=path.parent.parent/("rtw3-submarine-"+uuid.uuid4().hex+".tmp")
    try:
        with temporary.open("x",encoding="utf-8",newline="\n") as stream: json.dump(bindings,stream,indent=2,ensure_ascii=False);stream.write("\n")
        if json.loads(temporary.read_text(encoding="utf-8"))!=bindings: raise ValueError("Binding verification failed.")
        backup=saves.commit(path,output,expected_hash,[{"section":s,"key":k,"value":v} for (s,k),v in fields.items()])
        try:
            if mod_loader.running_games(): raise ValueError("RTW3 started during apply. Keep the backup and close the game before recovery.")
            if (binding_path.read_bytes() if binding_path.exists() else None)!=binding_raw: raise ValueError("Submarine bindings changed during apply.")
            temporary.replace(binding_path)
        except Exception as error:
            restored=False
            if not mod_loader.running_games() and saves.digest(path)==hashlib.sha256(output).hexdigest():
                restore=path.with_name(path.name+".submarine-restore-tmp")
                if restore.exists(): raise ValueError("Submarine recovery needs inspection. Full backup: "+str(backup))
                with restore.open("xb") as stream: stream.write(raw)
                restore.replace(path)
                restored=True
            raise ValueError(("Native save restored. " if restored else "Native changes may remain; close RTW3 and restore the full backup. ")
                             +"Submarine binding did not commit. Backup: "+str(backup)+". "+str(error)) from error
        return {"ok":True,"message":"Blueprint linked. Native availability/accuracy applied; reload this save. Tactical movement, custom tonnage and modern weapons are not changed.",
                "backup":str(backup),"binding_file":str(binding_path),"save":inspect_save(path,nation)}
    finally: temporary.unlink(missing_ok=True)
