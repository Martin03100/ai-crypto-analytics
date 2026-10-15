import subprocess, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W,H=1080,1920; B="/tmp/claude-0/sm/build"; OUT="/home/user/ai-crypto-analytics/social"
os.makedirs(OUT,exist_ok=True)
F="/usr/share/fonts/opentype/inter/"
def font(w,s): return ImageFont.truetype(F+("InterDisplay-Bold.otf" if w=="b" else "Inter-Medium.otf"),s)
BG=(11,13,18); ACC=(56,189,248); ACC2=(167,139,250); TXT=(240,242,247); SUB=(160,166,180)
def bg():
    im=Image.new("RGB",(W,H),BG); g=Image.new("RGB",(W,H),BG); d=ImageDraw.Draw(g)
    d.ellipse((-300,-200,700,800),fill=(20,60,90)); d.ellipse((500,1300,1400,2300),fill=(55,35,95))
    return Image.blend(im,g.filter(ImageFilter.GaussianBlur(220)),1.0)
def wrap(d,text,f,maxw):
    out=[]
    for para in text.split("\n"):
        line=""
        for w in para.split(" "):
            t=(line+" "+w).strip()
            if d.textlength(t,font=f)<=maxw: line=t
            else: out.append(line); line=w
        out.append(line)
    return out
def slide(name,title,sub=None,tag=None,hl=None):
    im=bg(); d=ImageDraw.Draw(im); y=640
    ft=font("b",104); lines=wrap(d,title,ft,920); y=H//2-(len(lines)*120+(0 if not sub else 260))//2
    if tag:
        fg=font("m",40); tw=d.textlength(tag,font=fg)
        d.rounded_rectangle((80,y-130,80+tw+60,y-60),radius=35,outline=ACC,width=3); d.text((110,y-122),tag,font=fg,fill=ACC)
    for l in lines:
        d.text((80,y),l,font=ft,fill=ACC if hl and any(l and l in h for h in hl) else TXT); y+=120
    if sub:
        y+=50
        for l in wrap(d,sub,font("m",52),920): d.text((80,y),l,font=font("m",52),fill=SUB); y+=70
    d.text((80,H-170),"AI Crypto Analytics",font=font("b",44),fill=TXT)
    d.text((80,H-110),"Not financial advice",font=font("m",34),fill=SUB)
    im.save(f"{B}/{name}.png")
def banner(name,text):
    im=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(im)
    lines=wrap(d,text,font("b",64),900); h=len(lines)*78+80
    d.rounded_rectangle((50,120,W-50,120+h),radius=36,fill=(11,13,18,235),outline=ACC,width=3)
    y=160
    for l in lines: d.text((90,y),l,font=font("b",64),fill=TXT); y+=78
    im.save(f"{B}/{name}.png")
# Input: a full-page 430px-wide (2.5x) dark-mode screenshot of the landing page.
home=Image.open("/tmp/claude-0/sm/shots/home.png").convert("RGB"); home=home.resize((W,int(home.height*W/home.width))); home.save(f"{B}/home.png")
def seg_img(src,out,d): subprocess.run(["ffmpeg","-y","-v","error","-loop","1","-i",src,"-t",str(d),"-vf","scale=1080:1920,format=yuv420p,fps=30","-c:v","libx264",out],check=True)
def seg_scroll(out,y0,y1,d,ban):
    vf=f"[0]crop=1080:1920:0:'{y0}+({y1}-{y0})*min(t/{d}\\,1)',fps=30[s];[s][1]overlay=0:0,format=yuv420p"
    subprocess.run(["ffmpeg","-y","-v","error","-loop","1","-i",f"{B}/home.png","-loop","1","-i",f"{B}/{ban}.png","-t",str(d),"-filter_complex",vf,"-c:v","libx264",out],check=True)
def concat(parts,out):
    # crossfade 0.4s between parts
    ins=[]; [ins.extend(["-i",p]) for p,_ in parts]
    fc=""; prev="0:v"; off=0
    for i in range(1,len(parts)):
        off+=parts[i-1][1]-0.4; lab=f"v{i}"
        fc+=f"[{prev}][{i}:v]xfade=transition=fade:duration=0.4:offset={off:.2f}[{lab}];"; prev=lab
    total=sum(d for _,d in parts)-0.4*(len(parts)-1)
    subprocess.run(["ffmpeg","-y","-v","error",*ins,"-f","lavfi","-t",f"{total:.2f}","-i","anullsrc=r=44100:cl=stereo","-filter_complex",fc.rstrip(";"),"-map",f"[{prev}]","-map",f"{len(parts)}:a","-c:v","libx264","-pix_fmt","yuv420p","-r","30","-c:a","aac","-shortest","-movflags","+faststart",out],check=True)
HH=home.height
def run(vid,spec):
    parts=[]
    for i,s in enumerate(spec):
        p=f"{B}/{vid}_{i}.mp4"
        if s[0]=="slide": slide(f"{vid}_{i}",*s[2]); seg_img(f"{B}/{vid}_{i}.png",p,s[1])
        else: banner(f"{vid}_b{i}",s[4]); seg_scroll(p,s[2],s[3],s[1],f"{vid}_b{i}")
        parts.append((p,s[1]))
    concat(parts,f"{OUT}/{vid}.mp4")
fy=lambda r:int(HH*r)
run("01_five_ais",[
 ("slide",3,("5 AIs predict crypto.\nWe check who was right.",None,"AI vs reality",["We check who was right."])),
 ("slide",3.5,("Gemini. GPT. Claude. DeepSeek. Grok.","Same coin, same moment, side by side.")),
 ("scroll",6,fy(0.0),fy(0.33),"5 AI models + real market data from 30+ sources"),
 ("slide",3.5,("Every forecast is checked against the real price.","No cherry-picking. Public track record.",None,["Every forecast is checked"])),
 ("slide",3.5,("Try it free","Link in bio · aicryptopredictor.netlify.app",None,["Try it free"])),
])
run("02_beat_the_ai",[
 ("slide",3,("Think you can beat the AI?",None,"Weekly challenge",["beat the AI?"])),
 ("slide",3.5,("Tip the final price.\nThe AI tips too.","Whoever is closer when the horizon ends wins.")),
 ("scroll",5,fy(0.30),fy(0.37),"Your tip vs AI — every week a new coin"),
 ("slide",3.5,("Win a badge on the public tipster board.","Free. No API key needed.")),
 ("slide",3.5,("Play this week","Link in bio",None,["Play this week"])),
])
run("03_honest_accuracy",[
 ("slide",3,("\"95% accurate\" crypto AI? Ask how it was measured.",None,"Honest numbers",["Ask how it was measured."])),
 ("slide",4,("A forecast can be saved only once, within 15 minutes.","Deleting it doesn't remove it from the stats.")),
 ("slide",4,("Every AI is compared with a naive guess:","\"the price stays the same\". If it can't beat that, you'll see it.")),
 ("scroll",5,fy(0.2),fy(0.32),"Measured accuracy, published for everyone"),
 ("slide",3.5,("See the live track record","Link in bio",None,["See the live track record"])),
])
