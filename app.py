import streamlit as st
import cv2
import numpy as np
from PIL import Image
import ezdxf
import tempfile
import os

st.set_page_config(page_title="مخطط وحاسب أحمال الليد المحترف", layout="wide")

st.title("📐 نظام تخطيط وحساب أحمال الليد المحترف (DXF)")
st.write("ارفع ملف الـ DXF لتوليد مسارات الليد الداخلية، حساب محيط التصميم الخارجي، وتفجير النصوص والكتل تلقائياً.")

col1, col2 = st.columns([1, 2])

with col1:
    st.header("⚙️ الإعدادات والمدخلات")
    uploaded_file = st.file_uploader("اختر ملف DXF...", type=["dxf"])
    
    if uploaded_file is not None:
        unit_choice = st.selectbox("وحدة الرسم في الملف الأصلية:", ["مليمتر (mm)", "سنتيمتر (cm)", "متر (m)"])
        
        st.subheader("🎛️ الهندسة والمسارات الداخلية")
        num_offsets = st.slider("عدد خطوط الليد الداخلية الإضافية:", min_value=0, max_value=5, value=1)
        offset_distance = st.slider("المسافة الفاصلة بين كل مسار والآخر (بوحدة الملف):", min_value=1.0, max_value=50.0, value=10.0, step=0.5)
        
        st.subheader("⚡ الحسابات الكهربائية الفعلية")
        led_watt_per_meter = st.number_input("استهلاك شريط الليد الفعلي (وات لكل متر W/m):", min_value=0.1, max_value=50.0, value=5.0, step=0.5)
        transformer_voltage = st.selectbox("فولتية النظام (الترانس والشريط):", [24, 12, 5])

with col2:
    if uploaded_file is not None:
        st.header("📊 مخطط المسارات والنتائج الهندسية والكهربائية")
        
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name
            
            doc = ezdxf.readfile(tmp_file_path)
            msp = doc.modelspace()
            
            # تفجير الكتل والنصوص لضمان قراءة الملفات غير المفرغة تلقائياً
            grouped_entities = msp.query('INSERT TEXT MTEXT DIMENSION')
            for entity in grouped_entities:
                try:
                    entity.explode()
                except:
                    pass
            
            perimeter_length_units = 0.0
            all_segments = []
            
            for entity in msp.query('*'):
                if entity.dxftype() == 'LINE':
                    p1 = (entity.dxf.start.x, entity.dxf.start.y)
                    p2 = (entity.dxf.end.x, entity.dxf.end.y)
                    all_segments.append((p1, p2))
                    perimeter_length_units += np.linalg.norm(np.array(p2) - np.array(p1))
                    
                elif entity.dxftype() == 'LWPOLYLINE':
                    pts = [(p[0], p[1]) for p in entity.get_points()]
                    if len(pts) > 1:
                        for i in range(len(pts) - 1):
                            all_segments.append((pts[i], pts[i+1]))
                            perimeter_length_units += np.linalg.norm(np.array(pts[i+1]) - np.array(pts[i]))
                        if entity.is_closed:
                            all_segments.append((pts[-1], pts[0]))
                            perimeter_length_units += np.linalg.norm(np.array(pts[-1]) - np.array(pts[0]))
                            
                elif entity.dxftype() == 'POLYLINE':
                    pts = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
                    if len(pts) > 1:
                        for i in range(len(pts) - 1):
                            all_segments.append((pts[i], pts[i+1]))
                            perimeter_length_units += np.linalg.norm(np.array(pts[i+1]) - np.array(pts[i]))
                        if entity.is_closed:
                            all_segments.append((pts[-1], pts[0]))
                            perimeter_length_units += np.linalg.norm(np.array(pts[-1]) - np.array(pts[0]))

                elif entity.dxftype() == 'CIRCLE':
                    cx, cy, r = entity.dxf.center.x, entity.dxf.center.y, entity.dxf.radius
                    num_segments = 64
                    angles = np.linspace(0, 2 * np.pi, num_segments + 1)
                    for i in range(num_segments):
                        x1, y1 = cx + r * np.cos(angles[i]), cy + r * np.sin(angles[i])
                        x2, y2 = cx + r * np.cos(angles[i+1]), cy + r * np.sin(angles[i+1])
                        all_segments.append(((x1, y1), (x2, y2)))
                    perimeter_length_units += 2 * np.pi * r

                elif entity.dxftype() == 'ARC':
                    cx, cy, r = entity.dxf.center.x, entity.dxf.center.y, entity.dxf.radius
                    start_angle = np.radians(entity.dxf.start_angle)
                    end_angle = np.radians(entity.dxf.end_angle)
                    if end_angle < start_angle:
                        end_angle += 2 * np.pi
                    num_segments = 32
                    angles = np.linspace(start_angle, end_angle, num_segments + 1)
                    for i in range(num_segments):
                        x1, y1 = cx + r * np.cos(angles[i]), cy + r * np.sin(angles[i])
                        x2, y2 = cx + r * np.cos(angles[i+1]), cy + r * np.sin(angles[i+1])
                        all_segments.append(((x1, y1), (x2, y2)))
                    perimeter_length_units += r * (end_angle - start_angle)

                elif entity.dxftype() == 'SPLINE':
                    try:
                        pts = [(p[0], p[1]) for p in entity.control_points]
                        if len(pts) > 1:
                            for i in range(len(pts) - 1):
                                all_segments.append((pts[i], pts[i+1]))
                                perimeter_length_units += np.linalg.norm(np.array(pts[i+1]) - np.array(pts[i]))
                    except:
                        pass

            os.unlink(tmp_file_path)
            
            if perimeter_length_units > 0:
                total_length_units = perimeter_length_units
                offset_segments = []
                
                for j in range(1, num_offsets + 1):
                    current_distance = j * offset_distance
                    for p1, p2 in all_segments:
                        np_p1 = np.array(p1, dtype=np.float64)
                        np_p2 = np.array(p2, dtype=np.float64)
                        
                        edge = np_p2 - np_p1
                        edge_len = np.linalg.norm(edge)
                        if edge_len > 0.0001:
                            normal = np.array([-edge[1], edge[0]]) / edge_len
                            offset_p1 = np_p1 + normal * current_distance
                            offset_p2 = np_p2 + normal * current_distance
                            offset_segments.append((offset_p1, offset_p2))
                            total_length_units += edge_len

                if unit_choice == "مليمتر (mm)":
                    perimeter_meters = perimeter_length_units / 1000
                    total_meters = total_length_units / 1000
                elif unit_choice == "سنتيمتر (cm)":
                    perimeter_meters = perimeter_length_units / 100
                    total_meters = total_length_units / 100
                else:
                    perimeter_meters = perimeter_length_units
                    total_meters = total_length_units

                net_wattage = total_meters * led_watt_per_meter
                required_transformer_wattage = net_wattage * 1.20
                required_amperage = required_transformer_wattage / transformer_voltage

                st.subheader("📊 إحصائيات المقاسات والأحمال الفعلية")
                
                st.metric(label="📐 محيط التصميم الخارجي (الهيكل الأساسي)", value=f"{perimeter_meters:.2f} متر")
                st.markdown("---")
                
                c_meters, c_watt, c_trans = st.columns(3)
                c_meters.metric(label="إجمالي أطوال خطوط الليد الكلية", value=f"{total_meters:.2f} متر")
                c_watt.metric(label="صافي استهلاك الليد الفعلي", value=f"{net_wattage:.1f} واط")
                c_trans.metric(label="قوة الترانس المطلوبة (+20% أمان)", value=f"{required_transformer_wattage:.1f} واط")
                
                st.info(f"⚡ **توصية الفني للورشة:** تحتاج إلى ترانس بقوة **{transformer_voltage} فولت** يعطي شدة تيار لا تقل عن **{required_amperage:.1f} أمبير** للتشغيل المستقر.")

                st.subheader("🗺️ مخطط مسارات الليد الهندسي (الأبيض: المحيط الخارجي | الأصفر: خطوط الليد الداخلية)")
                
                all_pts = []
                for p1, p2 in all_segments:
                    all_pts.extend([p1, p2])
                if all_pts:
                    all_pts = np.array(all_pts)
                    min_x, min_y = all_pts.min(axis=0), all_pts.min(axis=0)
                    max_x, max_y = all_pts.max(axis=0), all_pts.max(axis=0)
                    
                    img_w, img_h = 900, 650
                    drawing_board = np.zeros((img_h, img_w, 3), dtype=np.uint8)
                    
                    def scale_pt(pt):
                        span_x = (max_x[0] - min_x[0]) if (max_x[0] - min_x[0]) > 0 else 1
                        span_y = (max_y[1] - min_y[1]) if (max_y[1] - min_y[1]) > 0 else 1
                        x = int(50 + (pt[0] - min_x[0]) / span_x * (img_w - 100))
                        y = int((img_h - 50) - (pt[1] - min_y[1]) / span_y * (img_h - 100))
                        return (x, y)

                    for p1, p2 in all_segments:
                        cv2.line(drawing_board, scale_pt(p1), scale_pt(p2), (255, 255, 255), 2)
                    
                    for p1, p2 in offset_segments:
                        cv2.line(drawing_board, scale_pt(p1), scale_pt(p2), (0, 255, 255), 1)
                    
                    # استخدام use_column_width بدلاً من المقاطعة البرمجية القديمة لتفادي التنبيهات الصفراء بالواجهة
                    st.image(drawing_board, caption="مخطط توزيع مسارات الليد المحسوبة داخل الحرف", use_column_width=True)

            else:
                st.warning("⚠️ الملف لا يحتوي على خطوط هندسية صالحة للقياس.")
        except Exception as e:
            st.error(f"حدث خطأ أثناء معالجة وتخطيط الملف: {e}")