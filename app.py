import streamlit as st
import pandas as pd
import os
import io
from analyzer import PECDataAnalyzer  # استدعاء المحرك الذكي لـ PEC Marib

# 1. إعدادات الصفحة الأساسية المتجاوبة مع الكمبيوتر والجوال
st.set_page_config(
    page_title="نظام المراجعة الذكي - PEC Marib",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. حقن تصميم Glassmorphism والوضع الليلي الفاخر (Dark Mode)
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #f8fafc;
    }
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
    h1, h2, h3 {
        color: #38bdf8 !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    </style>
""", unsafe_allow_html=True)

# 3. دالة مخصصة لتلوين صفوف الجدول حسب نوع تصنيف الحالات
def highlight_rows(row):
    status = str(row.get('analysis_result', ''))
    if 'قفزة' in status:
        return ['background-color: rgba(239, 68, 68, 0.2)'] * len(row)
    elif 'انخفاض' in status:
        return ['background-color: rgba(234, 179, 8, 0.2)'] * len(row)
    elif 'اشتباه عداد' in status:
        return ['background-color: rgba(249, 115, 22, 0.2)'] * len(row)
    elif 'مستبعد' in status:
        return ['background-color: rgba(100, 116, 139, 0.2)'] * len(row)
    elif 'جديد' in status:
        return ['background-color: rgba(56, 189, 248, 0.2)'] * len(row)
    return [''] * len(row)

# 4. واجهة المستخدم الرئيسية
st.markdown("<h1 style='text-align: center;'>⚡ نظام المراجعة والتحليل الذكي للاستهلاك - PEC Marib</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #94a3b8;'>لوحة تحكم أونلاين لتحليل الانحراف المعياري عبر الروابط المباشرة للسيرفر</p>", unsafe_allow_html=True)

# إدخال وتحديد شهر الفوترة ورفع ملف الإكسل الحالي
col_month, col_upload = st.columns([1, 3])
with col_month:
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    target_month = st.selectbox("حدد شهر الفوترة الحالي:", [str(i).zfill(2) for i in range(1, 13)], index=5)
    st.markdown("</div>", unsafe_allow_html=True)

with col_upload:
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("قم برفع كشف الاستهلاك للشهر الحالي (Excel)", type=['xlsx', 'xls'])
    st.markdown("</div>", unsafe_allow_html=True)

# 5. تشغيل المعالجة فور رفع الملف الحالي
if uploaded_file is not None:
    with st.spinner('جاري سحب البيانات التاريخية من السيرفر وتشغيل خوارزميات الفرز...'):
        try:
            # حفظ ملف الإكسل المرفوع مؤقتاً في ذاكرة الخادم السحابي لإجراء الحسبة
            temp_excel_path = "temp_current_analysis.xlsx"
            with open(temp_excel_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # استدعاء المحرك الذكي (تعديل البش مهندس: لم نعد نمرر مسارات الـ json المحلية)
            engine = PECDataAnalyzer(excel_path=temp_excel_path, current_month_str=target_month)
            results_df = engine.analyze_current_month()
            
            # 6. عرض لوحة المؤشرات الرقمية السريعة
            st.markdown("<h3 style='margin-top: 30px;'>📊 لوحة المؤشرات والإحصائيات الفورية</h3>", unsafe_allow_html=True)
            m1, m2, m3, m4 = st.columns(4)
            
            with m1:
                st.markdown(f"<div class='glass-card'><h4>إجمالي المشتركين</h4><h2>{len(results_df)}</h2></div>", unsafe_allow_html=True)
            with m2:
                spikes = len(results_df[results_df['analysis_result'].str.contains('قفزة')])
                st.markdown(f"<div class='glass-card'><h4>قفزات غير منطقية</h4><h2 style='color:#ef4444;'>{spikes}</h2></div>", unsafe_allow_html=True)
            with m3:
                drops = len(results_df[results_df['analysis_result'].str.contains('انخفاض|اشتباه')])
                st.markdown(f"<div class='glass-card'><h4>هبوط / توقف العداد</h4><h2 style='color:#eab308;'>{drops}</h2></div>", unsafe_allow_html=True)
            with m4:
                new_accs = len(results_df[results_df['analysis_result'].str.contains('جديد')])
                st.markdown(f"<div class='glass-card'><h4>مشتركين جدد</h4><h2 style='color:#10b981;'>{new_accs}</h2></div>", unsafe_allow_html=True)

            # 7. عرض الجداول مقسمة بتبويبات تفاعلية للمستخدم
            st.markdown("### 📋 تفاصيل المراجعة والتحليل الميداني")
            tab1, tab2, tab3, tab4 = st.tabs(["🔴 الحالات الشاذة للمعاينة", "🔵 المشتركين الجدد", "⚪ الحسابات المستبعدة", "🟢 كافة الحسابات"])
            
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

            # 8. توليد وزر تصدير تقرير التفتيش النهائي لملف إكسل مخصص
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                results_df.to_excel(writer, index=False, sheet_name='PEC_Analysis')
            processed_data = output.getvalue()
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.download_button(
                label="📥 تحميل التقرير النهائي (Excel) لفرق التفتيش الميداني",
                data=processed_data,
                file_name=f"PEC_Analysis_Report_M{target_month}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            
            # تنظيف الذاكرة وحذف ملف الإكسل المؤقت
            if os.path.exists(temp_excel_path):
                os.remove(temp_excel_path)
                
        except Exception as e:
            st.error(f"حدث خطأ أثناء معالجة البيانات الإحصائية: {str(e)}")
else:
    st.info("💡 بانتظار قيام البش مهندس برفع كشف استهلاك الشهر الحالي للبدء الفوري...")