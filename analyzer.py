import pandas as pd
import numpy as np
import os
import warnings

# إخفاء التحذيرات لضمان نظافة المخرجات
warnings.filterwarnings('ignore')

class PECDataAnalyzer:
    def __init__(self, excel_path, json_paths, current_month_str):
        """
        تهيئة المحرك بمسارات الملفات والشهر الحالي المستهدف للتحليل.
        current_month_str: صيغة الشهر لاستخراج البيانات المطابقة (مثلاً '06' لشهر يونيو)
        """
        self.excel_path = excel_path
        self.json_paths = json_paths
        self.current_month_str = str(current_month_str).zfill(2)
        
    def load_historical_data(self):
        """جلب البيانات التاريخية وتطبيق شروط الاستثناء للاستهلاك الفعلي"""
        dfs = []
        for path in self.json_paths:
            if os.path.exists(path):
                # قراءة ملفات JSON (سطر بسطر كما هي مهيكلة)
                df_temp = pd.read_json(path, lines=True)
                dfs.append(df_temp)
            else:
                print(f"تنبيه: الملف {path} غير موجود!")
                
        if not dfs:
            raise ValueError("لم يتم العثور على أي بيانات تاريخية.")
            
        df_hist = pd.concat(dfs, ignore_index=True)
        
        # التأكد من أنواع البيانات لضمان دقة العمليات الحسابية
        df_hist['contract_no'] = df_hist['contract_no'].astype(str)
        df_hist['type_of_customer'] = df_hist['type_of_customer'].astype(str)
        df_hist['cur_consump'] = pd.to_numeric(df_hist['cur_consump'], errors='coerce').fillna(0)
        df_hist['mult_factor'] = pd.to_numeric(df_hist['mult_factor'], errors='coerce').fillna(1)
        
        # ---------------------------------------------------------
        # تطبيق شرط الاستثناء (الفئات 35, 43, 335, 343 باستهلاك 200)
        # ---------------------------------------------------------
        exception_types = ['35', '43', '335', '343']
        condition_exception = (df_hist['type_of_customer'].isin(exception_types)) & (df_hist['cur_consump'] == 200)
        
        # حساب الاستهلاك الفعلي التاريخي
        df_hist['historical_actual'] = np.where(
            condition_exception, 
            200, 
            df_hist['cur_consump'] * df_hist['mult_factor']
        )
        
        # تحويل فترة الفوترة إلى نوع تاريخ لاستخراج الشهر والترتيب
        df_hist['period_date'] = pd.to_datetime(df_hist['period'], format='%m-%Y', errors='coerce')
        df_hist['month'] = df_hist['period_date'].dt.strftime('%m')
        
        return df_hist

    def extract_latest_status(self, df_hist):
        """استخراج أحدث حالة مسجلة لكل مشترك (لتحديد الموقوفين وأصحاب الربط المباشر)"""
        # ترتيب البيانات تنازلياً حسب التاريخ لأخذ أحدث سجل
        df_latest = df_hist.sort_values('period_date', ascending=False).drop_duplicates(subset=['contract_no'], keep='first')
        
        return df_latest[['contract_no', 'meter_status', 'connection_type', 'type_of_customer', 'mult_factor']]

    def calculate_historical_baseline(self, df_hist):
        """حساب الوسيط (Median) والانحراف المطلق (MAD) لنفس الشهر خلال السنوات السابقة"""
        # فلترة البيانات لتطابق نفس الشهر المطلوب تحليله فقط
        df_same_month = df_hist[df_hist['month'] == self.current_month_str]
        
        # استبعاد الأشهر التي كان فيها العداد موقوفاً (6) أو ربط مباشر (2) تاريخياً من الحسبة
        df_valid_history = df_same_month[
            (df_same_month['meter_status'].astype(str) != '6') & 
            (df_same_month['connection_type'].astype(str) != '2')
        ]
        
        # تجميع البيانات لكل مشترك وحساب الوسيط والانحراف المطلق
        baseline = df_valid_history.groupby('contract_no')['historical_actual'].agg(
            hist_median='median',
            hist_mad=lambda x: np.median(np.abs(x - np.median(x)))
        ).reset_index()
        
        # معالجة الـ MAD الصفري لتفادي القسمة على صفر في Z-Score
        baseline['hist_mad'] = np.where(baseline['hist_mad'] == 0, 1.0, baseline['hist_mad'])
        
        return baseline

    def analyze_current_month(self):
        """الوظيفة الرئيسية: قراءة ملف الإكسل، دمج البيانات، وتصنيف المشتركين"""
        
        # 1. جلب وتجهيز البيانات التاريخية
        df_hist = self.load_historical_data()
        df_latest_status = self.extract_latest_status(df_hist)
        df_baseline = self.calculate_historical_baseline(df_hist)
        
        # 2. قراءة ملف إكسل الشهر الحالي
        df_current = pd.read_excel(self.excel_path)
        
        # إعادة تسمية الأعمدة لتسهيل التعامل برمجياً
        col_map = {
            'رقم المشترك': 'contract_no',
            'الاسم': 'customer_name',
            'الحرف او المربع': 'area_block',
            'الاستهلاك الشهري': 'current_consump'
        }
        df_current = df_current.rename(columns=col_map)
        df_current['contract_no'] = df_current['contract_no'].astype(str)
        df_current['current_consump'] = pd.to_numeric(df_current['current_consump'], errors='coerce').fillna(0)
        
        # 3. دمج بيانات الإكسل مع أحدث حالة تاريخية ومع الوسيط التاريخي
        df_merged = df_current.merge(df_latest_status, on='contract_no', how='left')
        df_merged = df_merged.merge(df_baseline, on='contract_no', how='left')
        
        # التعامل مع القيم الفارغة (للمشتركين الجدد)
        df_merged['meter_status'] = df_merged['meter_status'].fillna('2') # افتراض نشط للجديد
        df_merged['connection_type'] = df_merged['connection_type'].fillna('1') # افتراض عداد للجديد
        df_merged['mult_factor'] = df_merged['mult_factor'].fillna(1)
        
        # ---------------------------------------------------------
        # تطبيق شرط الاستثناء على الاستهلاك الحالي أيضاً (للمطابقة العادلة)
        # ---------------------------------------------------------
        exception_types = ['35', '43', '335', '343']
        cond_current_exc = (df_merged['type_of_customer'].isin(exception_types)) & (df_merged['current_consump'] == 200)
        
        df_merged['current_actual'] = np.where(
            cond_current_exc,
            200,
            df_merged['current_consump'] * df_merged['mult_factor']
        )
        
        # حساب مقياس Z-Score المعدل
        df_merged['z_score'] = (0.6745 * (df_merged['current_actual'] - df_merged['hist_median'])) / df_merged['hist_mad']
        df_merged['z_score'] = df_merged['z_score'].fillna(0).round(2)
        
        # 4. محرك التصنيف والشروط الذكية (Classification Logic)
        conditions = [
            (df_merged['connection_type'].astype(str) == '2'),  # استهلاك ثابت
            (df_merged['meter_status'].astype(str) == '6'),     # حساب موقوف
            (df_merged['hist_median'].isna()) & (df_merged['current_actual'] == 0), # جديد وصفر
            (df_merged['hist_median'].isna()) & (df_merged['current_actual'] > 0),  # جديد ببدء استهلاك
            (df_merged['hist_median'] > 0) & (df_merged['current_actual'] == 0),    # عداد ميت
            (df_merged['z_score'] > 2.5),                       # ارتفاع غير منطقي
            (df_merged['z_score'] < -2.5) & (df_merged['current_actual'] > 0)       # هبوط حاد
        ]
        
        choices = [
            'مستبعد - استهلاك ثابت',
            'مستبعد - حساب موقوف',
            'جديد - فترة تأسيس (استهلاك صفر)',
            'جديد - تأسيس خط أساس (بداية استهلاك)',
            'اشتباه عداد متوقف / عقار مغلق',
            'قفزة غير منطقية (مراجعة الإدخال)',
            'انخفاض حاد (اشتباه تلاعب)'
        ]
        
        df_merged['analysis_result'] = np.select(conditions, choices, default='طبيعي')
        
        # ترتيب الأعمدة للمخرجات النهائية
        final_columns = [
            'contract_no', 'customer_name', 'area_block', 'current_consump', 
            'current_actual', 'hist_median', 'z_score', 'analysis_result'
        ]
        
        return df_merged[final_columns]

# ==========================================
# منطقة التجربة (للتحقق من السكربت كملف مستقل)
# ==========================================
if __name__ == "__main__":
    # مسارات افتراضية (عدلها حسب مجلدك)
    EXCEL_FILE = "data/current_month.xlsx" 
    JSON_FILES = ["data/combined_bills_2.json", "data/combined_bills_3.json"]
    TARGET_MONTH = "06" # مثلاً شهر يونيو
    
    # التأكد من وجود الملفات قبل التشغيل
    if os.path.exists(EXCEL_FILE):
        analyzer = PECDataAnalyzer(EXCEL_FILE, JSON_FILES, TARGET_MONTH)
        result_df = analyzer.analyze_current_month()
        
        # حفظ النتيجة في ملف إكسل نظيف
        output_path = "data/Analysis_Report.xlsx"
        result_df.to_excel(output_path, index=False)
        print(f"تمت المعالجة بنجاح! تم حفظ التقرير في: {output_path}")
    else:
        print("ملف الإكسل غير موجود في المسار المحدد للتشغيل التجريبي.")