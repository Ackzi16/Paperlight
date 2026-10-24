"""Editable path geometry in unrotated page points, independent of UI pixels."""
import math
import pymupdf as f


def path_from_drawing(drawing):
    nodes=[];current=None
    def point(p):return [float(p.x),float(p.y)]
    def move(p):
        nonlocal current
        if current is None or abs(current-p)>.01:nodes.append(['M',*point(p)])
        current=p
    for item in drawing.get('items',[]):
        op=item[0]
        if op=='l':move(item[1]);nodes.append(['L',*point(item[2])]);current=item[2]
        elif op=='c':move(item[1]);nodes.append(['C',*point(item[2]),*point(item[3]),*point(item[4])]);current=item[4]
        elif op in ('re','qu'):
            if op=='re':
                r=item[1];pts=[r.tl,r.tr,r.br,r.bl]
                if len(item)>2 and item[2]<0:pts=[r.tl,r.bl,r.br,r.tr]
            else:q=item[1];pts=[q.ul,q.ur,q.lr,q.ll]
            nodes.append(['M',*point(pts[0])]);nodes.extend(['L',*point(p)] for p in pts[1:]);nodes.append(['Z']);current=None
        else:return []
    if drawing.get('closePath') and nodes and nodes[-1][0]!='Z':nodes.append(['Z'])
    return nodes


def valid_path(nodes):
    if not isinstance(nodes,list) or not 2<=len(nodes)<=5000:return False
    for node in nodes:
        if not isinstance(node,list) or not node or len(node)!={'M':3,'L':3,'C':7,'Z':1}.get(node[0],0):return False
        if any(not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>1e7 for v in node[1:]):return False
    return nodes[0][0]=='M'


def anchors(nodes):
    return [(n,j,('control' if node[0]=='C' and j<5 else 'anchor'),f.Point(node[j],node[j+1])) for n,node in enumerate(nodes) for j in range(1,len(node),2)]


def quad_for_path(nodes,rect):
    curves=[n for n in nodes if n[0]=='C']
    if nodes and nodes[0][0]=='M' and len(curves)==4:
        p0=f.Point(*nodes[0][1:]);p1=f.Point(*curves[0][5:]);p2=f.Point(*curves[1][5:]);p3=f.Point(*curves[2][5:])
        center=(p0+p2)/2;u=p0-center;v=p1-center
        if abs((p1+p3)/2-center)<.1 and abs(u)>0 and abs(v)>0:
            if u.x<0 or (abs(u.x)<.0001 and u.y<0):u=-u
            if u.x*v.y-u.y*v.x<0:v=-v
            return [center-u-v,center+u-v,center+u+v,center-u+v]
    points=[p for _,_,_,p in anchors(nodes)]
    if len(nodes)>=4 and nodes[0][0]=='M' and all(n[0]=='L' for n in nodes[1:4]):
        pts=[f.Point(*n[1:]) for n in nodes[:4]]
        if abs((pts[0]+pts[2])-(pts[1]+pts[3]))<.1:return pts
    direction=next((p-points[0] for p in points[1:] if abs(p-points[0])>.1),f.Point(1,0)) if points else f.Point(1,0)
    u=direction/abs(direction);v=f.Point(-u.y,u.x)
    if not points:points=[f.Rect(rect).tl,f.Rect(rect).br]
    xs=[p.x*u.x+p.y*u.y for p in points];ys=[p.x*v.x+p.y*v.y for p in points]
    x0,x1=min(xs),max(xs);y0,y1=min(ys),max(ys)
    if x1-x0<.1:x0-=1.5;x1+=1.5
    if y1-y0<.1:y0-=1.5;y1+=1.5
    return [u*x+v*y for x,y in ((x0,y0),(x1,y0),(x1,y1),(x0,y1))]


def rotation_matrix(quad,degrees):
    center=sum((f.Point(*p) for p in quad),f.Point())/4
    return f.Matrix(1,0,0,1,-center.x,-center.y)*f.Matrix(degrees)*f.Matrix(1,0,0,1,center.x,center.y)


def angle(quad):
    v=f.Point(*quad[1])-f.Point(*quad[0]);return math.degrees(math.atan2(v.y,v.x))


def path_operators(nodes,inverse):
    from pypdf.generic import FloatObject
    result=[]
    for node in nodes:
        points=[f.Point(node[i],node[i+1])*inverse for i in range(1,len(node),2)]
        values=[FloatObject(v) for point in points for v in point]
        result.append((values,{'M':b'm','L':b'l','C':b'c','Z':b'h'}[node[0]]))
    return result
