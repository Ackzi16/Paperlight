"""Document typography discovery and font-aware PDF text layout."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
import math
from pathlib import Path
import re
import statistics

import pymupdf as fitz


BASE14 = {
    'helvetica':'helv', 'helveticabold':'hebo', 'helveticaoblique':'heit',
    'helveticaboldoblique':'hebi', 'timesroman':'tiro', 'timesbold':'tibo',
    'timesitalic':'tiit', 'timesbolditalic':'tibi', 'courier':'cour',
    'courierbold':'cobo', 'courieroblique':'coit', 'courierboldoblique':'cobi',
    'symbol':'symb', 'zapfdingbats':'zadb',
}


def clean_name(name):
    return re.sub(r'^[A-Z]{6}\+', '', name or '')


def normalized(name):
    name=clean_name(name).lower().replace('psmt','').replace('mt','')
    return re.sub(r'[^a-z0-9\u3400-\u9fff]','',name)


@lru_cache(maxsize=1)
def installed_fonts():
    fonts=[]
    try:
        import winreg
        import os
        folder=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
        for hive in [winreg.HKEY_LOCAL_MACHINE,winreg.HKEY_CURRENT_USER]:
            try:
                with winreg.OpenKey(hive,r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts') as key:
                    for n in range(winreg.QueryInfoKey(key)[1]):
                        title,value,_=winreg.EnumValue(key,n)
                        if not isinstance(value,str):
                            continue
                        path=Path(value)
                        if not path.is_absolute():
                            path=folder/path
                        if path.exists():
                            title=re.sub(r'\s*\([^)]*\)\s*','',title)
                            fonts.append((normalized(title),str(path)))
            except OSError:
                continue
    except ImportError:
        pass
    return tuple(fonts)


@lru_cache(maxsize=128)
def system_font(name):
    target=normalized(name)
    candidates=[path for title,path in installed_fonts() if title==target]
    # Common PostScript names differ slightly from registry family names.
    aliases={'arialitalic':'arialitalic','timesnewromanps':'timesnewroman',
             'timesnewromanpsbold':'timesnewromanbold',
             'timesnewromanpsitalic':'timesnewromanitalic',
             'timesnewromanpsbolditalic':'timesnewromanbolditalic'}
    alias=aliases.get(target)
    if alias is None and target.endswith('regular'):
        alias=target[:-7]
    candidates += [path for title,path in installed_fonts() if alias and title==alias]
    for path in dict.fromkeys(candidates):
        try:
            return fitz.Font(fontfile=path)
        except Exception:
            continue
    return None


@dataclass
class FontChoice:
    name: str
    count: int=0
    xrefs: list[int]=field(default_factory=list)
    sizes: Counter=field(default_factory=Counter)
    colors: Counter=field(default_factory=Counter)
    flags: int=0
    buffer: bytes=b''
    embedded_font: object=None

    def resolve(self,text=''):
        """Prefer the original program, then an installed copy of the same face."""
        candidates=[]
        if self.embedded_font is not None:
            candidates.append((self.embedded_font,'Embedded PDF font'))
        builtin=BASE14.get(normalized(self.name))
        if builtin:
            candidates.append((fitz.Font(builtin),'Standard PDF font'))
        installed=system_font(self.name)
        if installed is not None:
            candidates.append((installed,'Installed copy of PDF font'))
        for font,source in candidates:
            if font.is_writable and all(char.isspace() or font.has_glyph(ord(char),fallback=False) for char in text):
                return font,source,False
        if candidates:
            for font,source in candidates:
                if font.is_writable:
                    return font,source+' · fallback for missing glyphs',True
        # An unembedded unavailable face has no font program to recover. Be explicit.
        bold,italic=bool(self.flags & 16),bool(self.flags & 2)
        variants={
            True:{(False,False):'tiro',(True,False):'tibo',(False,True):'tiit',(True,True):'tibi'},
            False:{(False,False):'helv',(True,False):'hebo',(False,True):'heit',(True,True):'hebi'},
        }
        fallback=fitz.Font(variants[bool(self.flags & 4)][bold,italic])
        return fallback,'Original font unavailable · readable substitute',True


@dataclass
class TextStyle:
    choice: FontChoice
    size: float=12.0
    color: tuple=(0,0,0)
    line_height: float=14.4
    align: str='left'
    anchor: tuple|None=None
    rotation: int=0
    matched: bool=False


def rgb(number):
    return ((number>>16 & 255)/255,(number>>8 & 255)/255,(number & 255)/255)


class FontCatalog:
    def __init__(self,doc):
        self.doc=doc
        self.choices=[]
        self.by_name={}
        self.entries=[]
        flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES
        for n,page in enumerate(doc):
            # OCR search layers describe recognition output, not the typeface
            # printed in a scan. Never let invisible text win font frequency.
            invisible=set()
            for trace in page.get_texttrace():
                if trace.get('type')==3 and trace.get('chars'):
                    origin=trace['chars'][0][2]
                    invisible.add((normalized(trace['font']),round(origin[0],1),round(origin[1],1)))
            resources=page.get_fonts(full=True)
            resource_map={normalized(row[3]):row[0] for row in resources}
            for block in page.get_text('dict',flags=flags)['blocks']:
                for line in block.get('lines',[]):
                    for span in line['spans']:
                        name=clean_name(span['font'])
                        # OCR search layers have no reliable visual typography.
                        if 'glyphless' in name.lower() or not span['text'].strip():
                            continue
                        if (normalized(name),round(span['origin'][0],1),round(span['origin'][1],1)) in invisible:
                            continue
                        key=normalized(name)
                        if key not in self.by_name:
                            self.by_name[key]=FontChoice(name=name,flags=span['flags'])
                        choice=self.by_name[key]
                        weight=max(1,len(span['text'].strip()))
                        choice.count+=weight
                        choice.sizes[round(span['size'],2)]+=weight
                        choice.colors[span['color']]+=weight
                        xref=resource_map.get(key)
                        # Span names can be truncated; accept a unique resource prefix.
                        if xref is None:
                            matches=[row[0] for row in resources if normalized(row[3]).startswith(key)]
                            if len(set(matches))==1:
                                xref=matches[0]
                        if xref and xref not in choice.xrefs:
                            choice.xrefs.append(xref)
                        self.entries.append((n,span,line.get('dir',(1,0)),block['number']))
        self.choices=sorted(self.by_name.values(),key=lambda c:(-c.count,c.name))
        if not self.choices:
            self.choices=[FontChoice('Helvetica',sizes=Counter({12.:1}),colors=Counter({0:1}))]
        for choice in self.choices:
            for xref in choice.xrefs:
                try:
                    _,_,_,buffer=doc.extract_font(xref)
                    if buffer:
                        font=fitz.Font(fontbuffer=buffer)
                        if font.is_writable:
                            choice.buffer=buffer
                            choice.embedded_font=font
                            break
                except Exception:
                    continue

    def style(self,page_index,rect=None):
        rect=fitz.Rect(rect) if rect is not None else None
        selected=[]
        for n,span,direction,block in self.entries:
            if n!=page_index:
                continue
            if rect is not None and not fitz.Rect(span['bbox']).intersects(rect):
                continue
            selected.append((span,direction,block))
        # Adding text to an empty area uses document frequency rather than an
        # arbitrary nearby caption. Corrections use the selected spans' frequency.
        if rect is not None and selected:
            weights=Counter()
            for span,_,_ in selected:
                intersection=fitz.Rect(span['bbox']) & rect
                fraction=intersection.width/max(1,fitz.Rect(span['bbox']).width)
                weights[normalized(span['font'])]+=max(1,len(span['text'])*fraction)
            choice=self.by_name.get(weights.most_common(1)[0][0],self.choices[0])
            matching=[s for s,d,b in selected if normalized(s['font'])==normalized(choice.name)]
            span=max(matching,key=lambda s:len(s['text']))
            sizes=Counter()
            colors=Counter()
            for s in matching:
                sizes[round(s['size'],2)]+=len(s['text'])
                colors[s['color']]+=len(s['text'])
            size=sizes.most_common(1)[0][0]
            color=rgb(colors.most_common(1)[0][0])
            direction=next(d for s,d,b in selected if s is span)
            rotation=round(math.degrees(math.atan2(-direction[1],direction[0])))%360
            rotation=min([0,90,180,270],key=lambda r:abs(r-rotation))
            baselines=sorted(set(round(s['origin'][1],2) for s in matching))
            deltas=[b-a for a,b in zip(baselines,baselines[1:]) if size*.8<b-a<size*2.5]
            line_height=statistics.median(deltas) if deltas else size*1.2
            # Locate the first selected character, preserving original baseline
            # and horizontal start even when the rectangle selects part of a span.
            anchor=None
            raw=self.doc[page_index].get_text('rawdict',flags=fitz.TEXTFLAGS_RAWDICT & ~fitz.TEXT_PRESERVE_IMAGES)
            for block in raw['blocks']:
                for line in block.get('lines',[]):
                    for s in line['spans']:
                        for char in s['chars']:
                            r=fitz.Rect(char['bbox'])
                            if rect.contains(fitz.Point((r.x0+r.x1)/2,(r.y0+r.y1)/2)):
                                anchor=tuple(char['origin'])
                                break
                        if anchor:
                            break
                    if anchor:
                        break
                if anchor:
                    break
            align='left'
            line_bounds={}
            for s in matching:
                y=round(s['origin'][1],1)
                line_bounds[y]=line_bounds.get(y,fitz.Rect()) | fitz.Rect(s['bbox'])
            bounds=list(line_bounds.values())
            if len(bounds)>1 and max(r.width for r in bounds)-min(r.width for r in bounds)>4:
                centers=[(r.x0+r.x1)/2 for r in bounds]
                ends=[r.x1 for r in bounds]
                if max(centers)-min(centers)<1.5:
                    align='center'
                elif max(ends)-min(ends)<1.5:
                    align='right'
            return TextStyle(choice,size,color,line_height,align=align,anchor=anchor,rotation=rotation,matched=True)
        choice=self.choices[0]
        size=choice.sizes.most_common(1)[0][0] if choice.sizes else 12.
        color=rgb(choice.colors.most_common(1)[0][0]) if choice.colors else (0,0,0)
        return TextStyle(choice,size,color,size*1.2)


def wrap_text(text,font,size,width):
    lines=[]
    for paragraph in text.split('\n'):
        current=''
        for char in paragraph:
            if font.text_length(current+char,fontsize=size)>width+.05:
                if not current:
                    raise ValueError('The text does not fit. Widen the box or reduce the font size.')
                cut=current.rfind(' ')
                if cut>0 and char!=' ':
                    lines.append(current[:cut])
                    current=current[cut+1:]+char
                else:
                    lines.append(current.rstrip())
                    current=char.lstrip()
            else:
                current+=char
        lines.append(current)
    return lines


def insert_styled_text(page,rect,text,style):
    font,source,substituted=style.choice.resolve(text)
    rect=fitz.Rect(rect)
    # Horizontal layout preserves the selected baseline; page rotation is already
    # handled by the canvas. Text rotated inside a page uses a local text box.
    if style.rotation:
        # Reuse the embedded font via a normal rotated insertion.
        resource='PL'+str(page.parent.xref_length())
        page.insert_font(fontname=resource,fontbuffer=font.buffer)
        remaining=page.insert_textbox(rect,text,fontname=resource,fontsize=style.size,
                                     color=style.color,rotate=style.rotation,
                                     align={'left':0,'center':1,'right':2}.get(style.align,0),
                                     lineheight=style.line_height/style.size)
        if remaining<0:
            raise ValueError('The text does not fit in the selected rectangle.')
        return
    x=rect.x0
    baseline=rect.y0+font.ascender*style.size
    if style.anchor:
        x=max(rect.x0,min(style.anchor[0],rect.x1-1))
        baseline=style.anchor[1]
    lines=wrap_text(text,font,style.size,rect.x1-x)
    bottom=baseline+(len(lines)-1)*style.line_height-font.descender*style.size
    # Font bboxes may include an unused descender. Permit the same tight box that
    # already held a matched original line, while rejecting actual extra lines.
    allowance=style.size*.15 if style.matched and len(lines)==1 else .5
    if bottom>rect.y1+allowance:
        raise ValueError('The text does not fit. Enlarge the box or reduce the font size.')
    writer=fitz.TextWriter(page.rect,color=style.color)
    builtin=BASE14.get(normalized(style.choice.name)) if source=='Standard PDF font' and not substituted else None
    for n,line in enumerate(lines):
        if not line:
            continue
        width=font.text_length(line,fontsize=style.size)
        left=x
        if style.align=='center':
            left=rect.x0+(rect.width-width)/2
        elif style.align=='right':
            left=rect.x1-width
        point=(left,baseline+n*style.line_height)
        if builtin:
            page.insert_text(point,line,fontname=builtin,fontsize=style.size,color=style.color,overlay=True)
        else:
            writer.append(point,line,font=font,fontsize=style.size)
    if not builtin:
        writer.write_text(page,color=style.color,overlay=True)
