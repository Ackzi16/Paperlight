"""Object-mode interactions, separate from reading and markup gestures."""
import math
import pymupdf as fitz
from PySide6.QtCore import Qt,QPointF
from PySide6.QtGui import QColor,QPen,QBrush,QPainterPath,QTransform
from PySide6.QtWidgets import QMenu,QColorDialog,QInputDialog,QGraphicsPathItem,QGraphicsEllipseItem,QGraphicsPixmapItem
from .i18n import t
from .objects import object_identity

class ObjectCanvasMixin:
    def object_init(self):
        self.page_objects=[];self.object_items=[];self.selected_object=None
        self.object_hover=None;self.object_drag=None;self.object_key=None
        self.outline_items=[];self.handles=[];self.guide_items=[];self.point_mode=False
        self.preview_items=[];self.preview_original=None;self.preview_identity=None
        self.preview_layers=None;self.preview_scale=1;self.commit_pending=False
        self.preview_path_item=None;self.reselect_target=None;self.text_draft_identity=None

    def object_rect(self,obj,rect=None):
        r=fitz.Rect(rect if rect is not None else obj.rect)*~self.page_transform
        return (r.x0*self.factor+self.page_origin.x(),r.y0*self.factor+self.page_origin.y(),r.width*self.factor,r.height*self.factor)

    def page_scene(self,p):
        p=fitz.Point(p)*~self.page_transform
        return QPointF(p.x*self.factor+self.page_origin.x(),p.y*self.factor+self.page_origin.y())

    def object_quad(self,obj):
        if obj.quad:return [fitz.Point(*p) for p in obj.quad]
        r=fitz.Rect(obj.rect)
        if obj.kind=='text':r.x1=min(self.page_bounds.x1,r.x1+8)
        return [r.tl,r.tr,r.br,r.bl]

    def movable_object(self,obj):
        return bool(obj and obj.writable and obj.kind in ('shape','image','text','ocr','annotation') and (obj.kind!='text' or (tuple(self.page_transform)==tuple(fitz.Identity) and all(tuple(s['direction'])==(1.,0.) for s in obj.spans))))

    def remove_visuals(self,items):
        from shiboken6 import isValid
        for item in items:
            if isValid(item):self.scene().removeItem(item)
        items.clear()

    def set_page_objects(self,objects,key):
        from shiboken6 import isValid
        if key!=self.object_key or any(not isValid(item) for item in self.outline_items):
            self.remove_visuals(self.outline_items);self.remove_visuals(self.handles);self.remove_visuals(self.guide_items)
            self.selected_object=None;self.object_hover=None;self.object_drag=None;self.point_mode=False
        self.object_key=key;self.page_objects=objects
        self.paint_objects()

    def painter_path(self,nodes):
        path=QPainterPath()
        for node in nodes:
            values=[self.page_scene(fitz.Point(node[i],node[i+1])) for i in range(1,len(node),2)]
            if node[0]=='M':path.moveTo(values[0])
            elif node[0]=='L':path.lineTo(values[0])
            elif node[0]=='C':path.cubicTo(*values)
            elif node[0]=='Z':path.closeSubpath()
        return path

    def paint_objects(self,preview=None):
        from shiboken6 import isValid
        if self.mode!='edit':
            self.remove_visuals(self.outline_items);self.remove_visuals(self.handles);self.remove_visuals(self.guide_items);self.clear_edit_preview();return
        if any(not isValid(item) for item in self.outline_items):self.outline_items=[]
        while len(self.outline_items)<len(self.page_objects):
            item=QGraphicsPathItem();item.setZValue(30);self.scene().addItem(item);self.outline_items.append(item)
        for n,obj in enumerate(self.page_objects):
            selected=obj is self.selected_object;hover=obj is self.object_hover
            matrix=self.object_drag['matrix'] if selected and self.object_drag else fitz.Identity
            item=self.outline_items[n]
            stamp=(self.factor,self.page_origin.x(),self.page_origin.y(),selected,hover,tuple(matrix),repr(self.object_drag.get('path')) if selected and self.object_drag else None)
            if getattr(item,'render_stamp',None)==stamp:continue
            item.render_stamp=stamp;item.pdf_object=obj
            points=[p*matrix for p in self.object_quad(obj)]
            if selected and self.object_drag and self.object_drag.get('path') is not None:
                from .geometry import quad_for_path
                points=quad_for_path(self.object_drag['path'],obj.rect)
            if selected and obj.kind=='shape' and obj.path:
                nodes=self.object_drag.get('path') if self.object_drag else None
                if nodes is None:
                    nodes=[[node[0],*[v for i in range(1,len(node),2) for v in (fitz.Point(node[i],node[i+1])*matrix)]] for node in obj.path]
                path=self.painter_path(nodes)
            else:
                path=QPainterPath();path.moveTo(self.page_scene(points[0]))
                for point in points[1:]:path.lineTo(self.page_scene(point))
                path.closeSubpath()
            color=QColor('#2878d4' if selected or hover else '#a0aab5' if obj.writable else '#b4a694')
            item=self.outline_items[n];item.setPath(path)
            item.setPen(QPen(color,1.5 if selected or hover else .65,Qt.PenStyle.SolidLine if selected else Qt.PenStyle.DashLine))
        self.update_handles()

    def controls(self):
        obj=self.selected_object
        if not self.movable_object(obj):return []
        if self.point_mode and obj.kind=='shape' and obj.path:
            from .geometry import anchors
            nodes=self.object_drag.get('path') if self.object_drag else None
            return [('node',(n,j),kind,self.page_scene(p)) for n,j,kind,p in anchors(nodes or obj.path)]
        matrix=self.object_drag['matrix'] if self.object_drag else fitz.Identity
        quad=[self.page_scene(p*matrix) for p in self.object_quad(obj)]
        result=[('corner',n,'anchor',p) for n,p in enumerate(quad)]
        if obj.kind in ('text','ocr','annotation'):return result
        center=sum(quad,QPointF())/4;top=(quad[0]+quad[1])/2;v=top-center
        length=math.hypot(v.x(),v.y()) or 1
        result.append(('rotate',0,'rotation',top+v*(27/length)))
        return result

    def update_handles(self):
        from shiboken6 import isValid
        if any(not isValid(item) for item in self.handles):self.handles=[]
        controls=self.controls()
        while len(self.handles)<len(controls):
            handle=QGraphicsEllipseItem(-4,-4,8,8);handle.setZValue(34);self.scene().addItem(handle);self.handles.append(handle)
        for n,item in enumerate(self.handles):
            item.setVisible(n<len(controls))
            if n<len(controls):
                kind,_,style,p=controls[n];item.setPos(p)
                item.setPen(QPen(QColor('#2878d4'),1));item.setBrush(QBrush(QColor('#2878d4' if style=='control' else 'white')))
        segments=[]
        if self.point_mode and self.selected_object and self.selected_object.path:
            nodes=self.object_drag.get('path') if self.object_drag else None;nodes=nodes or self.selected_object.path
            last=None
            for node in nodes:
                if node[0]=='C' and last is not None:
                    for a,b in ((last,fitz.Point(*node[1:3])),(fitz.Point(*node[5:7]),fitz.Point(*node[3:5]))):
                        pa,pb=self.page_scene(a),self.page_scene(b)
                        segments.append((pa,pb))
                if node[0] in ('M','L'):last=fitz.Point(*node[1:3])
                elif node[0]=='C':last=fitz.Point(*node[5:7])
        elif controls and controls[-1][0]=='rotate':
            quad=[self.page_scene(p*(self.object_drag['matrix'] if self.object_drag else fitz.Identity)) for p in self.object_quad(self.selected_object)]
            top=(quad[0]+quad[1])/2;end=controls[-1][-1]
            segments.append((top,end))
        if any(not isValid(item) for item in self.guide_items):self.guide_items=[]
        while len(self.guide_items)<len(segments):
            line=self.scene().addLine(0,0,0,0,QPen(QColor('#7fa6d0'),.8));line.setZValue(32);self.guide_items.append(line)
        for n,line in enumerate(self.guide_items):
            line.setVisible(n<len(segments))
            if n<len(segments):
                a,b=segments[n];line.setLine(a.x(),a.y(),b.x(),b.y())

    def object_keypress(self,event):
        if self.mode!='edit':return False
        delta={Qt.Key.Key_Left:(-1,0),Qt.Key.Key_Right:(1,0),Qt.Key.Key_Up:(0,-1),Qt.Key.Key_Down:(0,1)}.get(event.key())
        obj=self.selected_object
        if not delta or not self.movable_object(obj) or self.commit_pending:return False
        step=10 if event.modifiers()&Qt.KeyboardModifier.ShiftModifier else 1
        self.commit_pending=True
        self.object_changed.emit(dict(obj=obj,transform=(1,0,0,1,delta[0]*step,delta[1]*step)))
        return True

    def object_hit(self,point,cycle=False):
        hits=[];margin=5/self.factor
        for obj in self.page_objects:
            if (fitz.Rect(obj.rect)+(-margin,-margin,margin,margin)).contains(point):hits.append(obj)
        priority={'form':0,'annotation':1,'text':2,'ocr':2,'shape':3,'image':4}
        hits.sort(key=lambda o:(priority[o.kind],fitz.Rect(o.rect).get_area()))
        if cycle and self.selected_object in hits:return hits[(hits.index(self.selected_object)+1)%len(hits)]
        return hits[0] if hits else None

    def object_press(self,event):
        if self.mode!='edit':return False
        if event.button()==Qt.MouseButton.RightButton:self.object_menu.emit(event.globalPosition().toPoint());return True
        if event.button()!=Qt.MouseButton.LeftButton or self.commit_pending:return True
        if not self.commit_draft():return True
        point=self.pdf_point(event.position().toPoint());scene=self.mapToScene(event.position().toPoint());control=None
        for candidate in self.controls():
            if abs(scene.x()-candidate[-1].x())<9 and abs(scene.y()-candidate[-1].y())<9:control=candidate;break
        obj=self.selected_object if control else self.object_hit(point,bool(event.modifiers()&Qt.KeyboardModifier.AltModifier))
        changed=obj is not self.selected_object
        if changed:self.clear_edit_preview();self.point_mode=False
        self.object_click_point=point;self.setFocus();self.selected_object=obj;self.paint_objects()
        if obj is not None and obj.kind not in ('text','ocr','annotation'):self.object_chosen.emit(obj)
        if not self.movable_object(obj):return True
        if changed or self.preview_identity!=object_identity(obj):self.preview_requested.emit(obj)
        quad=self.object_quad(obj);center=sum(quad,fitz.Point())/4
        self.object_drag=dict(obj=obj,start=point,quad=quad,center=center,control=control,matrix=fitz.Matrix(1,1),path=None,changed=False)
        return True

    def move_node(self,drag,point,modifiers):
        import copy
        nodes=copy.deepcopy(drag['obj'].path);n,j=drag['control'][1]
        old=fitz.Point(nodes[n][j],nodes[n][j+1]);delta=point-drag['start']
        if modifiers&Qt.KeyboardModifier.ShiftModifier:
            if abs(delta.x)>abs(delta.y):delta.y=0
            else:delta.x=0
        target=old+delta;nodes[n][j:j+2]=list(target)
        if j==1 and nodes[n][0]=='M' and nodes[-1][0]=='Z':
            last=nodes[-2]
            if last[0]=='C' and abs(fitz.Point(*last[5:7])-old)<.1:
                last[5:7]=list(target);last[3:5]=list(fitz.Point(*last[3:5])+delta)
        if nodes[n][0]=='C' and j==5:nodes[n][3:5]=list(fitz.Point(*nodes[n][3:5])+delta)
        if drag['control'][2]=='anchor' and n+1<len(nodes) and nodes[n+1][0]=='C':nodes[n+1][1:3]=list(fitz.Point(*nodes[n+1][1:3])+delta)
        return nodes

    def object_move(self,event):
        if self.mode!='edit':return False
        drag=self.object_drag
        if drag and event.buttons()&Qt.MouseButton.LeftButton:
            point=self.pdf_point(event.position().toPoint());control=drag['control'];matrix=fitz.Matrix(1,1)
            if control and control[0]=='node':drag['path']=self.move_node(drag,point,event.modifiers())
            elif control and control[0]=='rotate':
                from .geometry import rotation_matrix
                a=drag['start']-drag['center'];b=point-drag['center']
                degrees=math.degrees(math.atan2(b.y,b.x)-math.atan2(a.y,a.x))
                if event.modifiers()&Qt.KeyboardModifier.ShiftModifier:degrees=round(degrees/15)*15
                matrix=rotation_matrix(drag['quad'],degrees)
            elif control and control[0]=='corner':
                q=drag['quad'];u=q[1]-q[0];v=q[3]-q[0];basis=fitz.Matrix(u.x,u.y,v.x,v.y,q[0].x,q[0].y)
                if abs(basis.a*basis.d-basis.b*basis.c)>1e-7:
                    local=point*~basis;index=control[1];opposite=((1,1),(0,1),(0,0),(1,0))[index]
                    original=((0,0),(1,0),(1,1),(0,1))[index]
                    sx=max(.03,(local.x-opposite[0])/(original[0]-opposite[0]));sy=max(.03,(local.y-opposite[1])/(original[1]-opposite[1]))
                    if event.modifiers()&Qt.KeyboardModifier.ShiftModifier:sx=sy=max(sx,sy)
                    resize=fitz.Matrix(sx,0,0,sy,opposite[0]*(1-sx),opposite[1]*(1-sy));matrix=~basis*resize*basis
            else:
                delta=point-drag['start'];matrix=fitz.Matrix(1,0,0,1,delta.x,delta.y)
            drag['matrix']=matrix;drag['changed']=abs(point-drag['start'])>.15
            if drag['obj'].kind in ('text','ocr','annotation'):
                drag['draft_started']=drag.get('draft_started',False) or drag['changed']
                if drag['draft_started']:self.object_changed.emit(dict(obj=drag['obj'],transform=tuple(matrix),draft=True))
                self.paint_objects();return True
            self.apply_preview_transform(matrix,drag.get('path'));self.paint_objects();return True
        hover=self.object_hit(self.pdf_point(event.position().toPoint()))
        if hover is not self.object_hover:self.object_hover=hover;self.paint_objects()
        scene=self.mapToScene(event.position().toPoint());handle=next((c for c in self.controls() if abs(scene.x()-c[-1].x())<9 and abs(scene.y()-c[-1].y())<9),None)
        cursor=Qt.CursorShape.CrossCursor if handle else Qt.CursorShape.ForbiddenCursor if hover and not hover.writable else Qt.CursorShape.IBeamCursor if hover and hover.kind in ('text','ocr') else Qt.CursorShape.SizeAllCursor if hover else Qt.CursorShape.ArrowCursor
        self.setCursor(cursor);return True

    def object_release(self,event):
        if self.mode!='edit':return False
        drag=self.object_drag;self.object_drag=None
        if drag and drag['changed']:
            self.commit_pending=True
            self.object_changed.emit(dict(obj=drag['obj'],transform=tuple(drag['matrix']),path=drag.get('path')))
        else:
            if drag and drag.get('draft_started'):self.object_changed.emit(dict(obj=drag['obj'],transform=tuple(fitz.Identity),cancel=True))
            self.paint_objects()
        return True

    def clear_edit_preview(self,restore=True):
        from shiboken6 import isValid
        if restore and self.preview_original:
            item,pixmap,scale=self.preview_original
            if isValid(item):item.setPixmap(pixmap);item.setScale(scale)
        self.remove_visuals(self.preview_items)
        self.preview_original=None;self.preview_identity=None;self.preview_layers=None;self.preview_path_item=None

    def active_page_item(self):
        return self.page_images.get(self.active_page) if self.continuous_doc is not None else getattr(self,'single_page_image',None)

    def accept_edit_frame(self,page,pixmap,scale):
        if self.continuous_doc is not None:item=self.page_images.get(page)
        else:item=getattr(self,'single_page_image',None) if page==self.active_page else None
        if item is not None:
            if not hasattr(self,'edit_raster_cache'):self.edit_raster_cache={}
            doc=self.continuous_doc
            source=str(doc.name) if doc is not None else getattr(self,'edit_source_path','')
            self.edit_raster_cache[(source,page)]=(pixmap,scale)
            while len(self.edit_raster_cache)>6:self.edit_raster_cache.pop(next(iter(self.edit_raster_cache)))
            self.clear_edit_preview(restore=False);item.setPixmap(pixmap);item.setScale(self.factor/scale)

    def accept_edit_preview(self,obj,layers):
        selected=self.selected_object
        if not selected or object_identity(selected)!=object_identity(obj):return
        item=self.active_page_item()
        if item is None:return
        self.clear_edit_preview();self.preview_original=(item,item.pixmap(),item.scale());self.preview_layers=layers
        self.preview_identity=object_identity(selected);self.preview_scale=layers['selected']['scale']
        item.setPixmap(layers['before']['pixmap']);item.setScale(self.factor/layers['before']['scale'])
        for name,z in (('selected',1),('after',2)):
            layer=layers[name];graphic=QGraphicsPixmapItem(layer['pixmap']);graphic.setOffset(layer['x'],layer['y']);graphic.setPos(self.page_origin)
            graphic.setScale(self.factor/layer['scale']);graphic.setZValue(z);self.scene().addItem(graphic);self.preview_items.append(graphic)
        if self.object_drag:self.apply_preview_transform(self.object_drag['matrix'],self.object_drag.get('path'))
        if self.object_drag and self.object_drag['changed'] and selected.kind in ('text','ocr','annotation'):self.preview_items[0].hide()
        if self.text_draft_identity==self.preview_identity:self.preview_items[0].hide()

    def apply_preview_transform(self,matrix,nodes=None):
        if not self.preview_items:return
        selected=self.preview_items[0]
        if nodes is not None:
            selected.hide()
            if self.preview_path_item is None:
                self.preview_path_item=QGraphicsPathItem();self.preview_path_item.setZValue(1);self.scene().addItem(self.preview_path_item);self.preview_items.append(self.preview_path_item)
            obj=self.selected_object;drawing=obj.drawing;stroke=drawing.get('color');fill=drawing.get('fill')
            pen=QPen(Qt.PenStyle.NoPen) if stroke is None else QPen(QColor.fromRgbF(*stroke),drawing.get('width',1)*self.factor)
            if stroke:pen.setCapStyle(Qt.PenCapStyle.RoundCap if max(drawing.get('lineCap',(0,0,0)))==1 else Qt.PenCapStyle.FlatCap)
            self.preview_path_item.setPath(self.painter_path(nodes));self.preview_path_item.setPen(pen)
            self.preview_path_item.setBrush(QBrush(Qt.BrushStyle.NoBrush) if fill is None else QBrush(QColor.fromRgbF(*fill)))
            return
        selected.show()
        if self.preview_path_item:self.preview_path_item.hide()
        scale=fitz.Matrix(self.preview_scale,self.preview_scale);rotation=~self.page_transform
        # Qt applies its scale property before the base transform. Compose the
        # display scale here so translation scales with the geometry as well.
        selected.setScale(1)
        display=~scale*~rotation*matrix*rotation*fitz.Matrix(self.factor,self.factor)
        selected.setTransform(QTransform(*tuple(display)))


class ObjectWindowMixin:
    def ensure_edit_ocr(self):
        if not self.session or self.canvas.mode!='edit' or self.job: return
        page=self.session.doc[self.page_index]
        row=self.records.get(self.page_index,{})
        key=(id(self.session),self.page_index,self.session.position)
        if row.get('complete') or key in getattr(self,'edit_ocr_attempts',set()): return
        if not page.get_image_info(): return
        if not hasattr(self,'edit_ocr_attempts'): self.edit_ocr_attempts=set()
        self.edit_ocr_attempts.add(key)
        self.start_index(True,apply_ocr=True,pages=[self.page_index])

    def update_page_objects(self):
        if not self.session or self.canvas.mode!='edit':
            self.edit_controller.stop();self.canvas.set_page_objects([],None);return
        key=(id(self.session),self.page_index,self.session.position,self.session._revision,self.canvas.factor,tuple(sorted(self.canvas.page_images)))
        if key!=getattr(self,'page_object_key',None):
            self.page_object_key=key;self.canvas.commit_pending=True
            self.edit_controller.refresh()

    def choose_object(self,obj):
        if obj is None: return
        if not obj.writable:
            self.status.setText(t(obj.reason));return
        if obj.kind=='form': self.fill_form(fitz.Rect(obj.rect).tl);return
        if obj.kind in ('text','ocr','annotation'):
            self.open_object_text(obj)
        else:
            self.status.setText(t('Drag to move. Drag a corner to resize or the round handle above to rotate. Right-click for Edit points and an exact angle.'))

    def open_object_text(self,obj):
        from .inline_text import InlineTextBox
        from .richtext import load
        from dataclasses import replace
        if not self.commit_inline_text(): return
        self.stop_index()
        catalog=self.session.font_catalog();style=catalog.style(self.page_index,obj.rect)
        if obj.kind=='text' and (self.session.doc[self.page_index].rotation or any(tuple(span['direction'])!=(1.,0.) for span in obj.spans)):
            self.status.setText(t('Rotate this page upright before editing this text box.'));return
        if obj.kind=='ocr':
            import statistics
            size=statistics.median(span['size'] for span in obj.spans) if obj.spans else max(7,min(24,fitz.Rect(obj.rect).height*.65))
            style=replace(style,anchor=None,size=size,line_height=size*1.25)
        rect=fitz.Rect(obj.rect)
        if obj.kind=='text':rect.x1=min((self.session.doc[self.page_index].rect*self.session.doc[self.page_index].derotation_matrix).x1,rect.x1+8)
        self.inline_text=InlineTextBox(self.canvas,rect,catalog,style,obj.text,rich=obj.kind=='text')
        box=self.inline_text;box.page_index=self.page_index;box.pdf_object=obj
        self.canvas.selected_object=obj;self.canvas.paint_objects()
        self.canvas.text_draft_identity=object_identity(obj)
        if self.canvas.preview_identity==self.canvas.text_draft_identity and self.canvas.preview_items:self.canvas.preview_items[0].hide()
        box.original_rect=fitz.Rect(box.rect);box.original_text=obj.text
        box.commit_requested.connect(self.commit_inline_text);box.cancel_requested.connect(self.cancel_inline_text)
        box.editor.textChanged.connect(self.update_actions)
        box.draft_changed.connect(self.update_actions)
        if box.rich: load(box,obj)
        box.editor.setFocus()
        point=getattr(self.canvas,'object_click_point',None)
        if point is not None:
            display=point*~self.canvas.page_transform
            view=self.canvas.mapFromScene(display.x*self.canvas.factor+self.canvas.page_origin.x(),display.y*self.canvas.factor+self.canvas.page_origin.y())
            local=box.editor.viewport().mapFrom(self.canvas.viewport(),view)
            box.editor.setTextCursor(box.editor.cursorForPosition(local))
        if self.canvas.preview_identity!=object_identity(obj):self.edit_controller.preview(obj)
        self.status.setText(t('Edit this text box directly. Resize changes wrapping. Three dots changes formatting. Ctrl+Enter applies; Escape cancels.'))

    def transform_object(self,data):
        if isinstance(data,tuple):obj,rect=data;options=dict(rect=rect)
        else:obj=data['obj'];options=dict(transform=data['transform'],path=data.get('path'))
        if obj.kind in ('text','ocr','annotation'):
            self.transform_text_box(obj,options,data if isinstance(data,dict) else {})
            return
        self.stop_index()
        if self.edit_controller.busy:self.edit_controller.stop()
        try:
            self.session.edit_object(self.page_index,obj,**options)
        except Exception as exc:
            self.canvas.commit_pending=False;self.canvas.clear_edit_preview();self.error(exc);return
        self.loaded_thumbs.discard(self.page_index)
        self.canvas.reselect_point_mode=self.canvas.point_mode
        self.canvas.reselect_target=(obj.kind,tuple(fitz.Rect(obj.rect)*fitz.Matrix(options.get('transform',(1,0,0,1,0,0)))))
        self.page_object_key=None;self.update_actions();self.update_page_objects()

    def transform_text_box(self,obj,options,data):
        if data.get('cancel'):
            self.cancel_inline_text();return
        box=self.inline_text
        if box is None or getattr(box,'pdf_object',None) is not obj:
            self.open_object_text(obj);box=self.inline_text
        if box is None:self.canvas.commit_pending=False;return
        matrix=fitz.Matrix(options.get('transform',(1,0,0,1,0,0)))
        rect=fitz.Rect(options['rect']) if 'rect' in options else box.original_rect*matrix
        if rect.width<8 or rect.height<8 or not self.canvas.page_bounds.contains(rect):
            self.canvas.commit_pending=False;return
        box.rect=rect;box.update_layout()
        for item in self.canvas.preview_items[:1]:item.hide()
        if data.get('draft'):
            self.canvas.setFocus();return
        self.canvas.reselect_target=('text' if obj.kind=='ocr' else obj.kind,tuple(rect))
        if not self.commit_inline_text():self.canvas.commit_pending=False

    def rotate_selected_object(self):
        obj=self.canvas.selected_object
        if not obj or obj.kind not in ('shape','image') or not obj.writable:return
        from .geometry import angle,rotation_matrix
        quad=self.canvas.object_quad(obj);current=angle(quad)
        value,ok=QInputDialog.getDouble(self,t('Rotate object'),t('Angle in degrees'),current,-3600,3600,1)
        if ok:self.transform_object(dict(obj=obj,transform=tuple(rotation_matrix(quad,value-current))))

    def toggle_point_editing(self):
        obj=self.canvas.selected_object
        if not obj or obj.kind!='shape' or not obj.path:return
        if sum(len(n)//2 for n in obj.path)>300:
            self.status.setText(t('This path has too many points for direct editing.'));return
        self.canvas.point_mode=not self.canvas.point_mode;self.canvas.paint_objects()
        if self.canvas.preview_identity!=object_identity(obj):self.edit_controller.preview(obj)
        self.status.setText(t('Drag anchors or curve handles. Shift constrains movement. Escape cancels a gesture.'))

    def delete_selected_object(self):
        obj=self.canvas.selected_object
        if not obj or not obj.writable or obj.kind=='form': return
        if self.inline_text: self.cancel_inline_text()
        if obj.kind in ('text','ocr'):
            self.mutate(lambda:self.session.object_text(self.page_index,obj,obj.rect,runs=[],text=''),purge=True,preserve=True,drop_rect=fitz.Rect(obj.rect))
        else: self.mutate(lambda:self.session.edit_object(self.page_index,obj,delete=True),preserve=True)

    def object_context_menu(self,position):
        obj=self.canvas.selected_object
        if not obj: return
        menu=QMenu(self);label=menu.addAction(t(obj.title));label.setEnabled(False)
        if obj.writable:
            if obj.kind in ('text','ocr','annotation'): menu.addAction(t('Edit text'),lambda:self.open_object_text(obj))
            if obj.kind in ('shape','image'):
                menu.addAction(t('Rotate object…'),self.rotate_selected_object)
            if obj.kind=='shape':
                if obj.path:menu.addAction(t('Edit points'),self.toggle_point_editing)
                menu.addAction(t('Stroke color'),lambda:self.object_color('stroke'))
                if obj.title!='Line': menu.addAction(t('Fill color'),lambda:self.object_color('fill'))
                menu.addAction(t('Stroke width'),self.object_width)
            if obj.kind!='form': menu.addAction(t('Delete object'),self.delete_selected_object)
        menu.exec(position)

    def object_color(self,part):
        obj=self.canvas.selected_object
        if not obj:return
        initial=obj.drawing.get('color' if part=='stroke' else 'fill') or (0,0,0)
        value=QColorDialog.getColor(QColor.fromRgbF(*initial[:3]),self,t('Color'))
        if value.isValid():
            self.mutate(lambda:self.session.edit_object(self.page_index,obj,**{part:(value.redF(),value.greenF(),value.blueF())}),preserve=True)

    def object_width(self):
        obj=self.canvas.selected_object
        if not obj:return
        value,ok=QInputDialog.getDouble(self,t('Stroke width'),t('Stroke width'),obj.drawing.get('width',1),.1,30,2)
        if ok:self.mutate(lambda:self.session.edit_object(self.page_index,obj,width=value),preserve=True)
