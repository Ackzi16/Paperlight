"""Page-space text selection for native characters and recognized OCR words."""
from dataclasses import dataclass
import re
import pymupdf as fitz


@dataclass
class TextUnit:
    text: str
    rect: tuple
    line: tuple
    direction: tuple=(1,0)
    separator: str=''


class PageText:
    def __init__(self,units=()):
        self.units=list(units)

    @classmethod
    def from_page(cls,page,ocr_words=()):
        groups=[]
        raw=page.get_text('rawdict',flags=fitz.TEXTFLAGS_RAWDICT & ~fitz.TEXT_PRESERVE_IMAGES,sort=True)
        for b,block in enumerate(raw['blocks']):
            for n,line in enumerate(block.get('lines',[])):
                units=[]
                for span in line['spans']:
                    for char in span['chars']:
                        units.append(TextUnit(char['c'],tuple(char['bbox']),('native',b,n),tuple(line['dir'])))
                if units:
                    box=fitz.Rect(line['bbox'])
                    groups.append((box.y0,box.x0,units))
        ocr_groups={}
        for word in ocr_words:
            if word.get('source')!='ocr' or not word['text'].strip():
                continue
            key=('ocr',word.get('block',0),word.get('line',0))
            box=fitz.Rect(word['rect'])
            ocr_groups.setdefault(key,[]).append(TextUnit(word['text'],tuple(box),key))
        for key,units in ocr_groups.items():
            units.sort(key=lambda u:u.rect[0])
            for previous,current in zip(units,units[1:]):
                cjk=lambda s: bool(s) and '\u3400'<=s<='\u9fff'
                current.separator='' if cjk(previous.text[-1]) and cjk(current.text[0]) else ' '
            groups.append((min(u.rect[1] for u in units),min(u.rect[0] for u in units),units))
        groups.sort(key=lambda group:(round(group[0],1),group[1]))
        result=[]
        for _,_,units in groups:
            if result:
                units[0].separator='\n'
            result.extend(units)
        return cls(result)

    def caret(self,point):
        if not self.units:
            return 0
        p=fitz.Point(point)
        def distance(unit):
            r=fitz.Rect(unit.rect)
            dx=max(r.x0-p.x,0,p.x-r.x1)
            dy=max(r.y0-p.y,0,p.y-r.y1)
            return dx*dx+dy*dy
        index=min(range(len(self.units)),key=lambda i:distance(self.units[i]))
        unit=self.units[index]
        rect=fitz.Rect(unit.rect)
        center=fitz.Point((rect.x0+rect.x1)/2,(rect.y0+rect.y1)/2)
        advance=(p.x-center.x)*unit.direction[0]+(p.y-center.y)*unit.direction[1]
        return index+(advance>=0)

    def contains(self,point):
        return any(fitz.Rect(u.rect).contains(point) for u in self.units)

    def text(self,start,end):
        start,end=sorted((start,end))
        selected=self.units[max(0,start):end]
        return ''.join((u.separator if n else '')+u.text for n,u in enumerate(selected)).replace('\xa0',' ')

    def rectangles(self,start,end):
        start,end=sorted((start,end))
        lines={}
        for unit in self.units[max(0,start):end]:
            lines[unit.line]=lines.get(unit.line,fitz.Rect()) | fitz.Rect(unit.rect)
        return list(lines.values())

    def word_range(self,caret):
        if not self.units:
            return 0,0
        index=min(max(caret,0),len(self.units)-1)
        if self.units[index].text.isspace() and index:
            index-=1
        word=lambda u: bool(re.search(r'\w',u.text))
        left,right=index,index+1
        while left>0 and self.units[left-1].line==self.units[index].line and not self.units[left].separator and word(self.units[left-1]):
            left-=1
        while right<len(self.units) and self.units[right].line==self.units[index].line and not self.units[right].separator and word(self.units[right]):
            right+=1
        return left,right
