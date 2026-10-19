from pathlib import Path
from PIL import Image, ImageDraw

root=Path(__file__).resolve().parent.parent
image=Image.new('RGBA',(256,256))
draw=ImageDraw.Draw(image)
draw.rounded_rectangle((8,8,248,248),radius=52,fill='#204f7d')
draw.rounded_rectangle((57,37,198,219),radius=10,fill='#f5f8fc')
draw.polygon([(155,37),(198,80),(155,80)],fill='#c8d9ec')
draw.line([(80,112),(170,112)],fill='#aac2dc',width=7)
draw.line([(80,137),(145,137)],fill='#aac2dc',width=7)
draw.line([(78,183),(95,165),(108,186),(133,156),(151,177),(175,164)],fill='#286baf',width=8,joint='curve')
image.save(root/'assets'/'paperlight.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
image.save(root/'assets'/'paperlight.png')
