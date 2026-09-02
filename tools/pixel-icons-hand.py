#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Два спрайта начинок, нарисованные РУКАМИ, а не сгенерированные (02.09, #157).

ПОЧЕМУ ОТДЕЛЬНО ОТ tools/pixel-icons.py. Тринадцать иконок из пятнадцати пришли из
Draw Things по тому пайплайну: генерация → посадка на сетку → палитра → ключевой цвет
в альфу. Две не пришли, и обе по своей причине — проверено глазами на одном кадре:

  · КРАБ-ПАЛОЧКА. Модель отдавала белую палку с красным бруском сбоку и торчащим
    треугольником: предмет не собирался, сколько ни менять формулировку.
  · НАРУТО. Модель рисовала гладкий белый диск с розовой спиралью — красиво и
    БЕСПОЛЕЗНО: в чипе 52 px он неотличим от майонеза, который тоже белый диск со
    спиралью. Настоящий наруто-маки имеет ЗУБЧАТЫЙ край, и именно край разводит эти
    две иконки на экране. Зубцы нарисованы формулой R = 13,2 + 1,5·cos(8φ).

То есть выбор не «рисовать красивее модели», а «иконка обязана отличаться от соседней
и изображать предмет». Где модель это давала — взято у неё.

Запуск: python3 tools/pixel-icons-hand.py play/assets/icons
"""
import struct, zlib, math, os, random, sys
S=40
def new(): return [[None]*S for _ in range(S)]
def put(im,x,y,c):
    x,y=int(round(x)),int(round(y))
    if 0<=x<S and 0<=y<S: im[y][x]=c
def poly(im,pts,c):
    ys=[p[1] for p in pts]
    for y in range(int(math.floor(min(ys))),int(math.ceil(max(ys)))+1):
        xs=[]
        for i in range(len(pts)):
            x1,y1=pts[i]; x2,y2=pts[(i+1)%len(pts)]
            if (y1<=y<y2) or (y2<=y<y1): xs.append(x1+(x2-x1)*(y-y1)/(y2-y1))
        xs.sort()
        for i in range(0,len(xs)-1,2):
            for x in range(int(math.ceil(xs[i])),int(math.floor(xs[i+1]))+1): put(im,x,y,c)
def ell(im,cx,cy,rx,ry,c):
    for y in range(int(cy-ry-1),int(cy+ry+2)):
        for x in range(int(cx-rx-1),int(cx+rx+2)):
            if ((x-cx)/rx)**2+((y-cy)/ry)**2<=1.0: put(im,x,y,c)
def line(im,x1,y1,x2,y2,c,w=1):
    n=int(max(abs(x2-x1),abs(y2-y1))*3)+1
    for i in range(n+1):
        t=i/n
        for dy in range(w):
            for dx in range(w): put(im,x1+(x2-x1)*t+dx-(w//2), y1+(y2-y1)*t+dy-(w//2), c)
def outline(im,c):
    src=[r[:] for r in im]
    for y in range(S):
        for x in range(S):
            if src[y][x] is not None: continue
            if any(0<=x+dx<S and 0<=y+dy<S and src[y+dy][x+dx] is not None
                   for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))): im[y][x]=c
def speck(im,seed,pairs,n=110):
    random.seed(seed)
    for _ in range(n):
        x=random.randint(0,S-1); y=random.randint(0,S-1)
        c=im[y][x]
        for a,b in pairs:
            if c==a and random.random()<0.5: im[y][x]=b; break
def save(im,p):
    rows=[]
    for y in range(S):
        r=bytearray()
        for x in range(S):
            c=im[y][x]; r += bytes(c) if c else b'\x00\x00\x00\x00'
        rows.append(b'\x00'+bytes(r))
    def ch(t,d):
        b=t+d; return struct.pack('>I',len(d))+b+struct.pack('>I',zlib.crc32(b))
    open(p,'wb').write(b'\x89PNG\r\n\x1a\n'+ch(b'IHDR',struct.pack('>IIBBBBB',S,S,8,6,0,0,0))
        +ch(b'IDAT',zlib.compress(b''.join(rows),9))+ch(b'IEND',b''))
def rgb(h): return (int(h[0:2],16),int(h[2:4],16),int(h[4:6],16),255)

OUT = (sys.argv[1] if len(sys.argv) > 1 else '.') + '/'
os.makedirs(OUT, exist_ok=True)

# ── КРАБ-ПАЛОЧКА: толстая палочка, красная шкурка сверху, белый срез с волокном ──
im=new()
body,shade,red,rdark = rgb('f5efe3'), rgb('cfc4ae'), rgb('d8403c'), rgb('a82826')
for t in range(101):
    u=t/100.0; cx=8.5+u*22; cy=28-u*15
    ell(im,cx,cy,6.0,6.0,body)
for t in range(101):                       # шкурка: верхняя треть окружности
    u=t/100.0; cx=8.5+u*22; cy=28-u*15
    for a in range(160,290,3):
        r=math.radians(a)
        for rr_ in (5.6,5.0,4.4):
            put(im,cx+rr_*math.cos(r),cy+rr_*math.sin(r),red)
for t in range(101):                       # тень снизу
    u=t/100.0; cx=8.5+u*22; cy=28-u*15
    for a in range(20,110,4):
        r=math.radians(a); put(im,cx+5.4*math.cos(r),cy+5.4*math.sin(r),shade)
ell(im,30.5,13,5.9,5.9,body)               # торец
for a in range(160,290,3):
    r=math.radians(a)
    for rr_ in (5.6,5.0):
        put(im,30.5+rr_*math.cos(r),13+rr_*math.sin(r),rdark)
for k in range(-3,4):                      # волокна на срезе
    line(im,30.5+k*1.3,8.6,30.5+k*1.3,17.4,shade)
outline(im,rgb('4a2320')); save(im,OUT+'kanikama.png')


# ── НАРУТО: белый кружок с розовой спиралью и волнистым краем ───────────────
im=new()
white,pink,plit = rgb('f5efe4'), rgb('e8697f'), rgb('f292a4')
cx,cy=20,20
for y in range(S):                                      # волнистый край: 8 зубцов
    for x in range(S):
        dx,dy=x-cx,y-cy; d=math.hypot(dx,dy)
        if d<1e-6: put(im,x,y,white); continue
        R=13.2+1.5*math.cos(8*math.atan2(dy,dx))
        if d<=R: put(im,x,y,white)
for t in range(0,760):                                  # спираль Архимеда, два витка
    a=math.radians(t*0.72); r=1.6+a*1.28
    if r>10.6: break
    put(im,cx+r*math.cos(a), cy+r*math.sin(a), pink)
    put(im,cx+(r+1)*math.cos(a), cy+(r+1)*math.sin(a), pink)
ell(im,cx,cy,1.6,1.6,plit)
outline(im,rgb('6b564c')); save(im,OUT+'naruto.png')


print('нарисовано:', sorted(f for f in os.listdir(OUT) if f in ('kanikama.png','naruto.png')))
