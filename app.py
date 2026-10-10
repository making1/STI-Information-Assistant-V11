from pathlib import Path
from datetime import datetime,timedelta
import csv,json,re,hashlib,uuid
import streamlit as st
import joblib,hmac,os
from sqlalchemy import create_engine,Column,Integer,String,Text,Boolean,DateTime,Float
from sqlalchemy.orm import declarative_base,sessionmaker

R=Path(__file__).resolve().parent
engine=create_engine(f"sqlite:///{R/'sti_app.db'}",connect_args={"check_same_thread":False})
Session=sessionmaker(bind=engine); Base=declarative_base()
class User(Base):
 __tablename__="users"; id=Column(Integer,primary_key=True); username=Column(String,unique=True,nullable=False); password_hash=Column(String,nullable=False); role=Column(String,default="admin"); active=Column(Boolean,default=True); created_at=Column(DateTime,default=datetime.utcnow)
class Content(Base):
 __tablename__="content"; id=Column(Integer,primary_key=True); topic=Column(String); language=Column(String); title=Column(String); body=Column(Text); source=Column(String); version=Column(String); status=Column(String,default="pending_review"); reviewer=Column(String); reviewed_at=Column(DateTime); created_at=Column(DateTime,default=datetime.utcnow); updated_at=Column(DateTime,default=datetime.utcnow)
class Inquiry(Base):
 __tablename__="inquiries"; id=Column(Integer,primary_key=True); session_hash=Column(String); language=Column(String); intent=Column(String); entities_json=Column(Text); raw_text=Column(Text); consent_to_store=Column(Boolean); created_at=Column(DateTime,default=datetime.utcnow)
class Audit(Base):
 __tablename__="audit_logs"; id=Column(Integer,primary_key=True); actor=Column(String); action=Column(String); object_type=Column(String); object_id=Column(String); details=Column(Text); created_at=Column(DateTime,default=datetime.utcnow)
class DemographicProfile(Base):
 __tablename__="demographic_profiles"; id=Column(Integer,primary_key=True); session_hash=Column(String,index=True); gender=Column(String); age_bracket=Column(String); sexually_active=Column(String); residence=Column(String); nearest_health_facility=Column(String); consent_to_store=Column(Boolean,default=False); created_at=Column(DateTime,default=datetime.utcnow)
class UsageSession(Base):
 __tablename__="usage_sessions"; id=Column(Integer,primary_key=True); session_id=Column(String,unique=True,index=True); user_hash=Column(String,index=True); started_at=Column(DateTime,default=datetime.utcnow); last_activity_at=Column(DateTime,default=datetime.utcnow); ended_at=Column(DateTime); user_messages=Column(Integer,default=0); assistant_responses=Column(Integer,default=0); completed_responses=Column(Integer,default=0); dropped_off=Column(Boolean,default=False)
class UsageEvent(Base):
 __tablename__="usage_events"; id=Column(Integer,primary_key=True); session_id=Column(String,index=True); user_hash=Column(String,index=True); event_type=Column(String,index=True); topic=Column(String,index=True); link_category=Column(String,index=True); created_at=Column(DateTime,default=datetime.utcnow)
def hash_password(password,salt=None):
 salt=salt or os.urandom(16)
 key=hashlib.pbkdf2_hmac("sha256",password.encode(),salt,200000)
 return f"pbkdf2_sha256$200000${salt.hex()}${key.hex()}"
def verify_password(password,stored):
 try:
  alg,it,salt_hex,key_hex=stored.split("$")
  key=hashlib.pbkdf2_hmac("sha256",password.encode(),bytes.fromhex(salt_hex),int(it))
  return hmac.compare_digest(key.hex(),key_hex)
 except Exception:return False
def secret_value(name,default=None):
 try:return st.secrets[name]
 except Exception:return os.environ.get(name,default)
def usage_ids():
 if "_usage_user" not in st.session_state: st.session_state["_usage_user"]=uuid.uuid4().hex
 if "_usage_session" not in st.session_state: st.session_state["_usage_session"]=uuid.uuid4().hex
 user_hash=hashlib.sha256(st.session_state["_usage_user"].encode()).hexdigest()[:24]
 return user_hash,st.session_state["_usage_session"]
def usage_event(event_type,topic=None,link_category=None):
 user_hash,sid=usage_ids(); db=Session(); now=datetime.utcnow()
 us=db.query(UsageSession).filter_by(session_id=sid).first()
 if not us:
  us=UsageSession(session_id=sid,user_hash=user_hash,started_at=now,last_activity_at=now)
  db.add(us);db.flush()
 us.last_activity_at=now
 if event_type=="user_message":us.user_messages=(us.user_messages or 0)+1
 elif event_type=="assistant_response":us.assistant_responses=(us.assistant_responses or 0)+1
 elif event_type=="response_completed":us.completed_responses=(us.completed_responses or 0)+1
 db.add(UsageEvent(session_id=sid,user_hash=user_hash,event_type=event_type,topic=topic,link_category=link_category,created_at=now))
 db.commit();db.close()
RESOURCE_ROUTES={
 "SYMPTOMS":["testing","referral"],"TESTING":["testing"],"WINDOW_PERIOD":["testing"],
 "PREVENTION":["prevention"],"TRANSMISSION":["prevention"],"TREATMENT":["referral"],
 "MEDICATION":["referral"],"EXPOSURE_RISK":["testing","prevention"],
 "URGENT_HEALTH_CONCERN":["referral"],"PARTNER_NOTIFICATION":["testing","referral"],
 "GENERAL_INFORMATION":["prevention","testing"],"MISCONCEPTION":["prevention"]
}
RESOURCE_LINKS={
 "testing":("STI testing and health services","https://www.health.go.ke/"),
 "prevention":("WHO STI prevention and information","https://www.who.int/health-topics/sexually-transmitted-infections"),
 "referral":("Kenya Ministry of Health services","https://www.health.go.ke/")
}
def route_resources(intent,entities):
 categories=list(RESOURCE_ROUTES.get(str(intent).upper(),["testing","prevention"]))
 if entities.get("symptoms") and "testing" not in categories:categories.insert(0,"testing")
 return categories
def tracked_link(label,url,category,key):
 # Streamlit cannot reliably observe clicks on ordinary markdown links, so use a button that records then opens the service.
 if st.button(label,key=key):
  usage_event("service_link_click",link_category=category)
  st.markdown(f"[Open {label}]({url})")
def boot():
 Base.metadata.create_all(engine); s=Session()
 admin_user=secret_value("ADMIN_USERNAME"); admin_password=secret_value("ADMIN_PASSWORD")
 # Deployment Secrets are authoritative: synchronize the admin on each restart.
 if admin_user and admin_password:
  configured=s.query(User).filter_by(role="admin").order_by(User.id).first()
  if configured:
   configured.username=admin_user
   configured.password_hash=hash_password(admin_password)
   configured.active=True
  else:
   s.add(User(username=admin_user,password_hash=hash_password(admin_password),role="admin",active=True))
 with open(R/"data/content_seed.csv",encoding="utf8") as f:
  for x in csv.DictReader(f):
   exists=s.query(Content.id).filter_by(topic=x["topic"],language=x["language"],title=x["title"]).first()
   if not exists:s.add(Content(topic=x["topic"],language=x["language"],title=x["title"],body=x["body"],source=x["source"],version=x["version"],status="pending_review"))
 s.commit(); s.close()
@st.cache_resource
def model():
 try:return joblib.load(R/"models/intent_model.joblib")
 except:return None
def classify_inquiry(question,trained):
 t=question.lower()
 rules=[
  ("URGENT_HEALTH_CONCERN",["severe pain","high fever","fainting","emergency","urgent care","immediate medical","severe pelvic","severe testicular"]),
  ("MEDICATION",["medicine","medication","antibiotic","antibiotics","prescription","drug for","leftover antibiotics"]),
  ("TESTING",["get tested","get a test","testing center","testing centre","where can i test","what test","test detects","do i need testing","seek an sti test","should i test"]),
  ("WINDOW_PERIOD",["window period","too early to test","how soon after","how long should i wait","when is testing reliable","when will an sti show"]),
  ("PARTNER_NOTIFICATION",["tell my partner","inform a sexual partner","partner notification","recent partners","partner need testing"]),
  ("MISCONCEPTION",["toilet seat","only promiscuous","by looking at","are stis always","i heard"]),
  ("SYMPTOMS",["symptoms","signs of","burning when","pain when i pee","discharge","genital sores"]),
  ("TRANSMISSION",["transmitted","how can someone catch","how does it spread","spread during sex"]),
  ("PREVENTION",["prevent","prevention","reduce my sti risk","safer sex","protect myself","condoms help"]),
  ("TREATMENT",["treated","treatment","cured","positive sti test"]),
  ("EXPOSURE_RISK",["my sti risk","how risky","possible sti exposure","condom broke","unprotected sex"]),
 ]
 for label,phrases in rules:
  if any(x in t for x in phrases):return label
 return str(trained.predict([question])[0]) if trained else "GENERAL_INFORMATION"
def concern_key(question):
 t=question.casefold()
 patterns=[
  ("urine_colour",r"\b(yellow|dark|orange|brown|cloudy)\s+urine\b|\burine\s+(?:is|looks|turned)\s+(?:yellow|dark|orange|brown|cloudy)\b|mkojo\s+wa\s+njano"),
  ("painful_urination",r"\b(pain|painful|burn|burning|stinging|hurts?)\b.{0,35}\b(urina(?:te|ting|tion)|pee|peeing|pass(?:ing)?\s+urine)\b|\b(painful urination|dysuria)\b|maumivu\s+nikikojoa"),
  ("genital_itching",r"\b(itch|itchy|itching|scratchy)\b.{0,35}\b(private parts?|genitals?|vagina|vulva|penis|groin)\b|\b(private parts?|genitals?|vagina|vulva|penis|groin)\b.{0,35}\b(itch|itchy|itching)\b|kuwashwa\s+sehemu\s+za\s+siri"),
  ("genital_discharge",r"\b(discharge|fluid|pus)\b.{0,35}\b(penis|vagina|genital|private parts?)\b|\b(penis|vagina|genital)\b.{0,35}\b(discharge|fluid|pus)\b"),
  ("genital_sores",r"\b(sores?|blisters?|ulcers?)\b.{0,35}\b(genital|penis|vagina|private parts?)\b")]
 for key,pattern in patterns:
  if re.search(pattern,t):return key
 return None

def approved_response(db,language,intent,entities,concern=None):
 """Select only explicitly approved content, matching intent before disease/general."""
 disease=entities.get("topics",[])
 keys=[]
 if concern:keys.append("concern:"+concern)
 for topic in disease:keys.append(f"{topic}:{intent.lower()}")
 keys.append(f"intent:{intent.lower()}")
 for topic in disease:keys.append(topic)
 if not concern:keys.append("general")
 for key in keys:
  found=db.query(Content).filter_by(topic=key,language=language,status="approved").order_by(Content.id).all()
  if found:return found,key
 return [],None
def redact(t):
 t=re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',"[email redacted]",t)
 return re.sub(r'(?<!\w)(?:\+?\d[\d\s\-()]{7,}\d)(?!\w)',"[phone/number redacted]",t)
def extract(t):
 x=t.lower(); o={"topics":[],"symptoms":[],"durations":[],"exposures":[]}
 maps=[("topics",{"gonorrhoea":["gonorrhoea","gonorrhea","kisonono"],"chlamydia":["chlamydia"],"syphilis":["syphilis","kaswende"],"hiv":["hiv","ukimwi"],"herpes":["herpes"],"hpv":["hpv"],"trichomoniasis":["trichomoniasis"]}),("symptoms",{"dysuria":["burning when urinating","burning when i pee","pain when urinating","pain when i pee","painful urination","kuungua nikikojoa","maumivu nikikojoa"],"genital_discharge":["yellow discharge","green discharge","penile discharge","vaginal discharge","discharge from penis","discharge from vagina","genital discharge","abnormal discharge","uchafu sehemu za siri","uchafu usio wa kawaida"],"pelvic_pain":["pelvic pain","maumivu ya nyonga"],"testicular_pain":["testicular pain","maumivu ya korodani"],"genital_sores":["genital sores","vidonda sehemu za siri"],"itching":["itching","kuwashwa"],"rash":["rash","upele"],"fever":["fever","homa"]}),("exposures",{"unprotected_sex":["unprotected sex","sex without condom","ngono bila kondomu"],"oral_sex":["oral sex","ngono ya mdomo"],"new_partner":["new partner","mwenza mpya"]})]
 for typ,mp in maps:
  for k,v in mp.items():
   if any(a in x for a in v):o[typ].append(k)
 o["durations"]=re.findall(r'\b\d+\s*(?:days?|weeks?|months?|siku|wiki|mwezi|miezi)\b',x); return o
def log(s,a,act,typ,oid="",d=""):s.add(Audit(actor=a,action=act,object_type=typ,object_id=str(oid),details=d))
boot(); st.set_page_config(page_title="STI Information Assistant",page_icon="🩺",layout="wide")
st.title("STI Information Assistant"); st.caption("Educational/research prototype — not a diagnostic or prescribing system.")
mode=st.sidebar.radio("Open",["Learner assistant","Admin"])
if mode=="Learner assistant":
 lang=st.selectbox("Language / Lugha",[("English","en"),("Kiswahili","sw")],format_func=lambda z:z[0])[1]
 st.info("Do not enter identifying information. Symptoms alone cannot confirm an STI." if lang=="en" else "Usiweke taarifa zinazokutambulisha. Dalili pekee haziwezi kuthibitisha STI.")
 st.subheader("Basic information" if lang=="en" else "Taarifa za msingi")
 st.caption("These fields are used only for aggregate research reporting. Avoid entering a home address." if lang=="en" else "Taarifa hizi hutumika tu kwa ripoti za jumla za utafiti. Usiweke anwani ya nyumbani.")
 c1,c2=st.columns(2)
 with c1:
  gender=st.selectbox("Gender" if lang=="en" else "Jinsia",["Prefer not to say","Male","Female","Other"])
  age_bracket=st.selectbox("Age bracket" if lang=="en" else "Kundi la umri",["Prefer not to say","18-19 years","20-22 years","23-25 years"])
  sexually_active=st.selectbox("Sexually active?" if lang=="en" else "Je, unashiriki ngono?",["Prefer not to say","Yes","No"])
 with c2:
  residence=st.text_input("Residence (county/town only)" if lang=="en" else "Makazi (kaunti/mji pekee)",placeholder="e.g. Nairobi")
  nearest_health_facility=st.text_input("Nearest health facility" if lang=="en" else "Kituo cha afya kilicho karibu",placeholder="e.g. local clinic or hospital")
 demographic_consent=st.checkbox("I consent to storing these basic details in de-identified form for aggregate research reporting." if lang=="en" else "Ninakubali taarifa hizi za msingi zihifadhiwe bila utambulisho kwa ripoti za jumla za utafiti.")
 if "_history" not in st.session_state:st.session_state["_history"]=[]
 st.subheader("Conversation history")
 for turn in st.session_state["_history"]:
  with st.chat_message(turn["role"]):st.markdown(turn["text"])
 if st.button("End conversation / Start new session"):
  if "_usage_session" in st.session_state:
   db=Session();record=db.query(UsageSession).filter_by(session_id=st.session_state["_usage_session"]).first()
   if record:record.ended_at=datetime.utcnow();db.commit()
   db.close()
  st.session_state["_history"]=[]
  st.session_state.pop("_usage_session",None)
  st.rerun()
 q=st.text_area("Ask an STI education question" if lang=="en" else "Uliza swali la elimu kuhusu STI",height=120,key=f"question_{len(st.session_state['_history'])}")
 consent=st.checkbox("I consent to storing a redacted copy for prototype evaluation." if lang=="en" else "Ninakubali nakala iliyofichwa taarifa binafsi ihifadhiwe kwa tathmini ya mfano huu.")
 if st.button("Process question" if lang=="en" else "Chambua swali",type="primary") and q.strip():
  m=model(); intent=classify_inquiry(q,m); e=extract(q); concern=concern_key(q)
  if concern:intent="SYMPTOMS"
  detected_topic=e["topics"][0] if e["topics"] else intent.lower()
  st.session_state["_history"].append({"role":"user","text":q})
  usage_event("user_message",topic=detected_topic)
  usage_event("intent_detected",topic=intent)
  for value in e.get("topics",[]): usage_event("sti_topic_detected",topic=value)
  for value in e.get("symptoms",[]): usage_event("symptom_detected",topic=value)
  for value in e.get("exposures",[]): usage_event("exposure_detected",topic=value)
  for value in e.get("durations",[]): usage_event("duration_detected",topic=value)
  # NLP extraction is internal and reported only in aggregate to administrators.
  s=Session();items,matched_key=approved_response(s,lang,intent,e,concern)
  topic=e["topics"][0] if e["topics"] else intent.lower()
  st.subheader("Educational information" if lang=="en" else "Taarifa za elimu")
  if not items:st.warning("No reviewer-approved content is available for this topic yet." if lang=="en" else "Bado hakuna maudhui yaliyoidhinishwa na mkaguzi kwa mada hii.")
  if matched_key=="general":st.caption("General STI education: topic-specific material is awaiting reviewer approval." if lang=="en" else "Elimu ya jumla ya STI: maudhui mahususi yanasubiri idhini ya mkaguzi.")
  for c in items:st.markdown(f"### {c.title}\n{c.body}"); st.caption(f"Source: {c.source} | Version: {c.version} | Reviewer: {c.reviewer}")
  if e["symptoms"]:st.warning("Symptoms alone do not establish an STI diagnosis. Consider professional assessment if symptoms persist or concern you." if lang=="en" else "Dalili hazithibitishi kisonono au STI nyingine. Fikiria kupata tathmini ya mhudumu wa afya na kipimo kinachofaa.")
  reply="\n\n".join(f"**{c.title}**\n\n{c.body}" for c in items) if items else ("No reviewer-approved educational content is available yet." if lang=="en" else "Bado hakuna maudhui yaliyoidhinishwa.")
  route_names={"testing":"testing services","prevention":"prevention resources","referral":"professional assessment/referral services"}
  recommended=", ".join(route_names[x] for x in route_resources(intent,e))
  reply=reply+"\n\n**Relevant STI resource services:** "+recommended+"."
  st.session_state["_history"].append({"role":"assistant","text":reply})
  usage_event("assistant_response",topic=topic);usage_event("response_completed",topic=topic)
  st.markdown("#### Recommended STI resource services" if lang=="en" else "#### Huduma za STI zinazopendekezwa")
  st.caption("Resources are selected according to the inquiry category. Links are informational, not appointments or verified facility referrals.")
  for category in route_resources(intent,e):
   label,url=RESOURCE_LINKS[category]
   tracked_link(label,url,category,f"resource_{category}_{len(st.session_state['_history'])}")
  user_hash,session_id=usage_ids()
  if consent:s.add(Inquiry(session_hash=session_id,language=lang,intent=intent,entities_json=json.dumps(e),raw_text=redact(q),consent_to_store=True))
  if demographic_consent:
   s.add(DemographicProfile(session_hash=session_id,gender=gender,age_bracket=age_bracket,sexually_active=sexually_active,residence=redact(residence.strip())[:100],nearest_health_facility=redact(nearest_health_facility.strip())[:150],consent_to_store=True))
  s.commit();s.close()
else:
 if not st.session_state.get("admin_ok"):
  configured_user=secret_value("ADMIN_USERNAME"); configured_password=secret_value("ADMIN_PASSWORD")
  if not configured_user or not configured_password:
   st.error("Admin login is not configured. Add ADMIN_USERNAME and ADMIN_PASSWORD in Streamlit App Settings > Secrets, save, then reboot the app.")
   st.stop()
  st.info("Use the ADMIN_USERNAME and ADMIN_PASSWORD currently configured in Streamlit Secrets.")
  u=st.text_input("Username"); p=st.text_input("Password",type="password")
  if st.button("Log in"):
   s=Session(); z=s.query(User).filter_by(username=u,active=True).first(); ok=z and verify_password(p,z.password_hash);s.close()
   if ok:st.session_state.admin_ok=True;st.session_state.admin_user=u;st.rerun()
   else:st.error("Invalid credentials.")
 else:
  actor=st.session_state.get("admin_user","admin"); st.success(f"Signed in as {actor}")
  if st.button("Log out"):st.session_state.admin_ok=False;st.rerun()
  t1,t2,t3,t4,t5,t6,t7,t8=st.tabs(["Review content","Create content","Approved content","Participant reporting","Usage analytics","Audit log","Privacy / retention","Account"])
  with t1:
   s=Session(); pending=s.query(Content).filter_by(status="pending_review").order_by(Content.id).all()
   st.caption("Approval must be performed by an actual qualified reviewer. The application does not manufacture expert approval.")
   for c in pending:
    with st.expander(f"#{c.id} [{c.language}] {c.title}"):
     st.write(c.body);st.caption(f"{c.source} | v{c.version}");rv=st.text_input("Reviewer name / role",key=f"r{c.id}");a,b=st.columns(2)
     if a.button("Approve",key=f"a{c.id}"):
      if not rv.strip():st.error("Enter the real reviewer name/role.")
      else:c.status="approved";c.reviewer=rv.strip();c.reviewed_at=datetime.utcnow();c.updated_at=datetime.utcnow();log(s,actor,"approve","content",c.id,f"reviewer={rv.strip()}");s.commit();st.rerun()
     if b.button("Archive",key=f"x{c.id}"):c.status="archived";c.updated_at=datetime.utcnow();log(s,actor,"archive","content",c.id);s.commit();st.rerun()
   s.close()
  with t2:
   with st.form("new"):
    tp=st.text_input("Topic",value="general");la=st.selectbox("Language",["en","sw"]);ti=st.text_input("Title");bo=st.text_area("Body");so=st.text_input("Source");ve=st.text_input("Version",value="1.0")
    if st.form_submit_button("Save as pending review"):
     s=Session();c=Content(topic=tp,language=la,title=ti,body=bo,source=so,version=ve,status="pending_review");s.add(c);s.flush();log(s,actor,"create","content",c.id,"pending_review");s.commit();s.close();st.success("Saved as pending_review.")
  with t3:
   s=Session()
   for c in s.query(Content).filter_by(status="approved").all():st.markdown(f"**#{c.id} [{c.language}] {c.title}**");st.write(c.body);st.caption(f"Reviewer: {c.reviewer} | Source: {c.source}")
   s.close()
  with t4:
   st.subheader("Aggregate participant reporting")
   st.caption("Only grouped counts are shown. Individual demographic records and inquiry text are not displayed together.")
   s=Session(); rows=s.query(DemographicProfile).filter_by(consent_to_store=True).all()
   st.metric("Consenting demographic records",len(rows))
   def counts(field):
    out={}
    for r in rows:
     v=getattr(r,field) or "Not provided";out[v]=out.get(v,0)+1
    return [{"category":k,"count":v} for k,v in sorted(out.items(),key=lambda x:(-x[1],x[0]))]
   a,b=st.columns(2)
   with a:
    st.markdown("**Gender**");st.dataframe(counts("gender"),use_container_width=True,hide_index=True)
    st.markdown("**Sexual activity**");st.dataframe(counts("sexually_active"),use_container_width=True,hide_index=True)
    st.markdown("**Residence**");st.dataframe(counts("residence"),use_container_width=True,hide_index=True)
   with b:
    st.markdown("**Age bracket**");st.dataframe(counts("age_bracket"),use_container_width=True,hide_index=True)
    st.markdown("**Nearest health facility**");st.dataframe(counts("nearest_health_facility"),use_container_width=True,hide_index=True)
   s.close()
  with t5:
   st.subheader("Routine-use behavioral analytics")
   st.caption("Automatically recorded pseudonymous interaction metrics. No post-interaction questionnaire is required.")
   db=Session(); sessions=db.query(UsageSession).all(); events=db.query(UsageEvent).all()
   unique_users=len(set(x.user_hash for x in sessions)); session_count=len(sessions)
   total_messages=sum((x.user_messages or 0) for x in sessions)
   turns=sum(min(x.user_messages or 0,x.assistant_responses or 0) for x in sessions)
   durations=[max(0,((x.last_activity_at or x.started_at)-x.started_at).total_seconds()) for x in sessions]
   avg_duration=(sum(durations)/len(durations)) if durations else 0
   by_user={}
   for x in sessions:by_user[x.user_hash]=by_user.get(x.user_hash,0)+1
   return_users=sum(1 for n in by_user.values() if n>1)
   completed=sum((x.completed_responses or 0) for x in sessions)
   responses=sum((x.assistant_responses or 0) for x in sessions)
   completion_rate=(100*completed/responses) if responses else 0
   # A conservative operational proxy: sessions with a user message but no completed assistant response.
   dropoffs=sum(1 for x in sessions if (x.user_messages or 0)>0 and (x.completed_responses or 0)==0)
   c1,c2,c3,c4=st.columns(4)
   c1.metric("Unique users",unique_users);c2.metric("Sessions",session_count);c3.metric("User messages",total_messages);c4.metric("Conversation turns",turns)
   c5,c6,c7,c8=st.columns(4)
   c5.metric("Return users",return_users);c6.metric("Avg. session duration",f"{avg_duration:.1f} sec");c7.metric("Response completion",f"{completion_rate:.1f}%");c8.metric("Conversation drop-off",dropoffs)
   st.markdown("**Frequency of return visits**")
   st.dataframe([{"sessions_per_user":n,"users":sum(1 for v in by_user.values() if v==n)} for n in sorted(set(by_user.values()))],use_container_width=True,hide_index=True)
   def event_counts(kind):
    out={}
    for e in events:
     if e.event_type==kind and e.topic:out[e.topic]=out.get(e.topic,0)+1
    return out
   intents=event_counts("intent_detected");sti_topics=event_counts("sti_topic_detected")
   symptoms=event_counts("symptom_detected");exposures=event_counts("exposure_detected");durations=event_counts("duration_detected")
   requested={};links={"testing":0,"prevention":0,"referral":0}
   for e in events:
    if e.event_type=="user_message" and e.topic:requested[e.topic]=requested.get(e.topic,0)+1
    if e.event_type=="service_link_click" and e.link_category:links[e.link_category]=links.get(e.link_category,0)+1
   def rows(data,label):return [{label:k,"count":v} for k,v in sorted(data.items(),key=lambda x:(-x[1],x[0]))]
   st.markdown("### Aggregated NLP information")
   a,b=st.columns(2)
   with a:
    st.markdown("**Inquiry intents**");st.dataframe(rows(intents,"intent"),use_container_width=True,hide_index=True)
    st.markdown("**STI topics explicitly mentioned**");st.dataframe(rows(sti_topics,"STI topic"),use_container_width=True,hide_index=True)
    st.markdown("**Symptoms mentioned**");st.dataframe(rows(symptoms,"symptom"),use_container_width=True,hide_index=True)
   with b:
    st.markdown("**Exposure indicators mentioned**");st.dataframe(rows(exposures,"exposure"),use_container_width=True,hide_index=True)
    st.markdown("**Durations mentioned**");st.dataframe(rows(durations,"duration"),use_container_width=True,hide_index=True)
    st.markdown("**Frequently requested information**");st.dataframe(rows(requested,"topic / intent"),use_container_width=True,hide_index=True)
   st.markdown("**Service-link interactions**");st.dataframe([{"service":k,"clicks":v} for k,v in links.items()],use_container_width=True,hide_index=True)
   st.caption("Drop-off is an operational proxy, not a clinical outcome. Session duration is measured from first to last recorded activity.")
   db.close()
  with t6:
   s=Session();st.dataframe([{"time":x.created_at,"actor":x.actor,"action":x.action,"object":f"{x.object_type}:{x.object_id}","details":x.details} for x in s.query(Audit).order_by(Audit.id.desc()).limit(200)],use_container_width=True);s.close()
  with t7:
   days=st.number_input("Delete stored inquiries older than N days",1,3650,90)
   if st.button("Run retention cleanup"):
    s=Session();cutoff=datetime.utcnow()-timedelta(days=int(days));n=s.query(Inquiry).filter(Inquiry.created_at<cutoff).delete();d=s.query(DemographicProfile).filter(DemographicProfile.created_at<cutoff).delete();ev=s.query(UsageEvent).filter(UsageEvent.created_at<cutoff).delete();us=s.query(UsageSession).filter(UsageSession.started_at<cutoff).delete();log(s,actor,"retention_cleanup","research_data","",f"inquiries={n}; demographics={d}; usage_events={ev}; usage_sessions={us}");s.commit();s.close();st.success(f"Deleted {n} inquiries, {d} demographic records, {ev} usage events and {us} usage sessions.")
  with t8:
   old=st.text_input("Current password",type="password");new=st.text_input("New password",type="password")
   if st.button("Change password"):
    s=Session();u=s.query(User).filter_by(username=actor).first()
    if not u or not verify_password(old,u.password_hash):st.error("Current password is incorrect.")
    elif len(new)<12:st.error("Use at least 12 characters.")
    else:u.password_hash=hash_password(new);log(s,actor,"password_change","user",u.id);s.commit();st.success("Password changed.")
    s.close()
