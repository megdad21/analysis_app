import streamlit as st
import pandas as pd
import os
import io
from analyzer import PECDataAnalyzer  # استدعاء المحرك اللي بنيناه في الملف الأول

# 1. إعدادات الصفحة الأساسية
st.set_page_config(
    page_title="نظام المراجعة الذكي - PEC Marib",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. حقن تصميم Glassmorphism والوضع الليلي (Dark Mode)
st.markdown("""
    <style>
    /* خلفية النظام العامة */
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #f8fafc;
    }
    
    /* تصميم بطاقات Glassmorphism */
    .glass-card {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 15px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    
    /* نصوص العناوين */
    h1, h2, h3 {
        color: #38bdf8 !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    </style>
""", unsafe_allow_html=True)

# 3. دالة مساعدة لتلوين الجداول بناءً على حالة المشترك
def highlight_rows(row):
    status = str(row.get('analysis_result', ''))
    if 'قفزة' in status:
        return ['background-color: rgba(239, 68, 68, 0.2)'] * len(row) # أحمر خفيف
    elif 'انخفاض' in status:
        return ['background-color: rgba(234, 179, 8, 0.2)'] * len(row) # أصفر خفيف
    elif 'اشتباه عداد' in status:
        return ['background-color: rgba(249, 115, 22, 0.2)'] * len(row) # برتقالي خفيف
    elif 'مستبعد' in status:
        return ['background-color: rgba(100, 116, 139, 0.2)'] * len(row) # رمادي
    elif 'جديد' in status:
        return ['background-color: rgba(56, 189, 248, 0.2)'] * len(row) # أزرق خفيف
    return [''] * len(row)

# 4. واجهة المستخدم الرئيسية
st.markdown("<h1 style='text-align: center;'>⚡ نظام المراجعة والتحليل الذكي للاستهلاك - PEC Marib</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #94a3b8;'>بوابة المطابقة وتحليل الانحراف المعياري باستخدام الوسيط المعدل (MAD)</p>", unsafe_allow_html=True)

# مسارات ملفات قاعدة البيانات التاريخية
JSON_PATHS = [
    os.path.join("data", "combined_bills_2.json"),
    os.path.join("data", "combined_bills_3.json")
]

# إدخال رقم الشهر المستهدف لضبط المقارنة
col_month, col_upload = st.columns([1, 3])
with col_month:
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    target_month = st.selectbox("حدد شهر الفوترة الحالي:", [str(i).zfill(2) for i in range(1, 13)], index=5) # افتراضي شهر 06
    st.markdown("</div>", unsafe_allow_html=True)

with col_upload:
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("قم برفع كشف الاستهلاك للشهر الحالي (Excel)", type=['xlsx', 'xls'])
    st.markdown("</div>", unsafe_allow_html=True)

# 5. معالجة البيانات عند رفع الملف
if uploaded_file is not None:
    with st.spinner('جاري مطابقة المفاتيح وتحليل البيانات التاريخية... يرجى الانتظار'):
        try:
            # التأكد من وجود مجلد data والملفات التاريخية
            for jp in JSON_PATHS:
                if not os.path.exists(jp):
                    st.error(f"خطأ: ملف قاعدة البيانات التاريخية '{jp}' غير موجود. تأكد من رفعه للمجلد.")
                    st.stop()
            
            # حفظ الملف المرفوع مؤقتاً لتمريره للمحرك
            temp_excel_path = os.path.join("data", "temp_current.xlsx")
            os.makedirs("data", exist_ok=True)
            with open(temp_excel_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # استدعاء المحرك وتشغيله
            engine = PECDataAnalyzer(excel_path=temp_excel_path, json_paths=JSON_PATHS, current_month_str=target_month)
            results_df = engine.analyze_current_month()
            
            # 6. عرض لوحة المؤشرات (Dashboards)
            st.markdown("<h3 style='margin-top: 30px;'>📊 لوحة المؤشرات والإحصائيات الفورية</h3>", unsafe_allow_html=True)
            m1, m2, m3, m4 = st.columns(4)
            
            with m1:
                st.markdown(f"<div class='glass-card'><h4 style='color:#cbd5e1;'>إجمالي المشتركين</h4><h2 style='color:#38bdf8;'>{len(results_df)}</h2></div>", unsafe_allow_html=True)
            with m2:
                spikes = len(results_df[results_df['analysis_result'].str.contains('قفزة')])
                st.markdown(f"<div class='glass-card'><h4 style='color:#cbd5e1;'>قفزات غير منطقية</h4><h2 style='color:#ef4444;'>{spikes}</h2></div>", unsafe_allow_html=True)
            with m3:
                drops = len(results_df[results_df['analysis_result'].str.contains('انخفاض|اشتباه')])
                st.markdown(f"<div class='glass-card'><h4 style='color:#cbd5e1;'>هبوط / توقف العداد</h4><h2 style='color:#eab308;'>{drops}</h2></div>", unsafe_allow_html=True)
            with m4:
                new_accs = len(results_df[results_df['analysis_result'].str.contains('جديد')])
                st.markdown(f"<div class='glass-card'><h4 style='color:#cbd5e1;'>مشتركين جدد</h4><h2 style='color:#10b981;'>{new_accs}</h2></div>", unsafe_allow_html=True)

            # 7. عرض الجداول مقسمة بتبويبات
            st.markdown("### 📋 تفاصيل المراجعة والتحليل")
            tab1, tab2, tab3, tab4 = st.tabs(["🔴 الحالات الشاذة (للتفتيش)", "🔵 المشتركين الجدد", "⚪ الحسابات المستبعدة", "🟢 الكل"])
            
            with tab1:
                anomalies_df = results_df[results_df['analysis_result'].str.contains('قفزة|انخفاض|اشتباه')]
                st.dataframe(anomalies_df.style.apply(highlight_rows, axis=1), use_container_width=True, height=400)
                
            with tab2:
                new_df = results_df[results_df['analysis_result'].str.contains('جديد')]
                st.dataframe(new_df.style.apply(highlight_rows, axis=1), use_container_width=True, height=400)
                
            with tab3:
                excluded_df = results_df[results_df['analysis_result'].str.contains('مستبعد')]
                st.dataframe(excluded_df.style.apply(highlight_rows, axis=1), use_container_width=True, height=400)

            with tab4:
                st.dataframe(results_df.style.apply(highlight_rows, axis=1), use_container_width=True, height=400)

            # 8. زر تصدير النتائج
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                results_df.to_excel(writer, index=False, sheet_name='Analysis_Results')
            processed_data = output.getvalue()
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.download_button(
                label="📥 تحميل التقرير النهائي (Excel) لفرق التفتيش",
                data=processed_data,
                file_name=f"PEC_Analysis_Report_M{target_month}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            
            # تنظيف الملف المؤقت
            if os.path.exists(temp_excel_path):
                os.remove(temp_excel_path)
                
        except Exception as e:
            st.error(f"حدث خطأ أثناء المعالجة: {str(e)}")
else:
    st.info("💡 بانتظار رفع كشف الشهر الحالي للبدء في التحليل...")