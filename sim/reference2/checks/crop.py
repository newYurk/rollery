import sys
from PIL import Image
src, dst = sys.argv[1], sys.argv[2]
l, t, r, b, sc = [float(v) for v in sys.argv[3:8]]
im = Image.open(src).convert('RGB')
W, H = im.size
box = (int(l*W), int(t*H), int(r*W), int(b*H))
im = im.crop(box)
im = im.resize((int(im.width*sc), int(im.height*sc)), Image.LANCZOS)
im.save(dst); print(dst, im.size)
