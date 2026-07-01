import sys, os, tempfile
sys.path.insert(0,'tools/mesh_gen')
import numpy as np, cv2
from psd_tools import PSDImage
from PIL import Image, ImageDraw, ImageFont
from rig_draft import build_rig

PSD='assets/robot_parts.psd'; PREFIX='機器人拆件'; MESH=['光暈','身體','左手']
FONT='/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'
fb=lambda s: ImageFont.truetype(FONT,s)

psd=PSDImage.open(PSD)
comp=np.array(psd.composite().convert('RGBA'))
W,H=psd.width,psd.height
rgb=comp[:,:,:3].astype(float); a=comp[:,:,3:4]/255.0
bg=(rgb*a+255*(1-a)).astype(np.uint8)   # RGB white-matte

def w2p(pt): return (int(pt[0]+W/2.0), int(H/2.0-pt[1]))
def pc(name,man):
    e=next(e for e in man['parts'] if e['name']==name)
    return (int(e['offset'][0]+e['size'][0]/2.0), int(e['offset'][1]+e['size'][1]/2.0))

def build(root_layer):
    d=tempfile.mkdtemp(); return build_rig(PSD,MESH,d,PREFIX,root_layer)

def render(root_layer, title, subtitle, sub_rgb):
    _,man,_,rep=build(root_layer)
    img=bg.copy()  # RGB
    root=rep['root']
    # shapes with cv2 (RGB array ok for shapes)
    for h in rep['hierarchy']:
        cpx=pc(h['part'],man)
        if h['parent'] is not None:
            cv2.line(img,cpx,pc(h['parent'],man),(255,255,255),3)
            cv2.line(img,cpx,pc(h['parent'],man),(40,40,40),1)
            if h['joint_pivot_draft'] is not None:
                jp=w2p(h['joint_pivot_draft'])
                cv2.circle(img,jp,12,(255,200,0),3); cv2.circle(img,jp,3,(255,200,0),-1)
    for h in rep['hierarchy']:
        cpx=pc(h['part'],man); is_root=(h['part']==root)
        col=(50,210,50) if is_root else (40,150,235)
        cv2.circle(img,cpx,8,col,-1); cv2.circle(img,cpx,8,(0,0,0),1)
    # header
    cv2.rectangle(img,(0,0),(W,64),(35,35,35),-1)
    # text via PIL
    pim=Image.fromarray(img); dr=ImageDraw.Draw(pim)
    dr.text((12,8),title,font=fb(26),fill=(255,255,255))
    dr.text((12,38),subtitle,font=fb(20),fill=sub_rgb)
    for h in rep['hierarchy']:
        cpx=pc(h['part'],man); is_root=(h['part']==root)
        tag=h['part']+('（ROOT）' if is_root else '')
        x,y=cpx[0]+11,cpx[1]-12
        dr.text((x,y),tag,font=fb(19),fill=(0,0,0))          # outline-ish
        dr.text((x-1,y-1),tag,font=fb(19),fill=(255,255,255))
    return np.array(pim), rep

fa,ra=render(None,'A) 自動選 root','＝ 光暈（背景件）　✗ 不建議',(255,80,80))
fb_img,rb=render('身體','B) 指定 root＝身體','軀幹為 root　✓ 建議',(80,210,80))

# legend band under both
def add_legend(img):
    pim=Image.fromarray(img); dr=ImageDraw.Draw(pim); y=H-66
    dr.rectangle([8,y-8,430,H-8],fill=(245,245,245),outline=(0,0,0))
    cv2.circle(img,(0,0),1,(0,0,0))  # noop
    return pim,dr,y
def legend(img):
    pim,dr,y=add_legend(img)
    a=np.array(pim)
    cv2.circle(a,(26,y+12),8,(50,210,50),-1)
    cv2.circle(a,(26,y+38),8,(40,150,235),-1)
    cv2.circle(a,(250,y+12),12,(255,200,0),3)
    cv2.line(a,(244,y+40),(262,y+40),(90,90,90),3)
    pim=Image.fromarray(a); dr=ImageDraw.Draw(pim)
    dr.text((40,y+2),'root bone（軀幹）',font=fb(17),fill=(0,0,0))
    dr.text((40,y+28),'part bone（件中心）',font=fb(17),fill=(0,0,0))
    dr.text((270,y+2),'pivot 草案（重疊質心）',font=fb(17),fill=(0,0,0))
    dr.text((270,y+28),'父子連結',font=fb(17),fill=(0,0,0))
    return np.array(pim)
fa=legend(fa); fb_img=legend(fb_img)

gap=np.full((H,16,3),255,np.uint8)
out=np.hstack([fa,gap,fb_img])
out=cv2.cvtColor(out,cv2.COLOR_RGB2BGR)
op='knowledge/figures/s5_rig_decision.png'
cv2.imwrite(op,out); print('wrote',op,out.shape)
