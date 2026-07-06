import pandas as pd
import numpy as np
import os
import warnings

warnings.filterwarnings('ignore')

class PECDataAnalyzer:
    def __init__(self, excel_path, current_month_str):
        """
        تعديل البش مهندس: سحب ملفات الـ JSON الكبيرة مباشرة عبر روابط سيرفر Hostinger
        """
        self.excel_path = excel_path
        self.current_month_str = str(current_month_str).zfill(2)
        
        # ضع روابط موقعك المباشرة هنا بدلاً من المسارات المحلية
        self.json_urls = [
            "https://pecmarib-ye.site/db_all/H_db/combined_bills_2.json",
            "https://pecmarib-ye.site/db_all/H_db/combined_bills_3.json"
        ]
        
    def load_historical_data(self):
        """جلب البيانات التاريخية من روابط السيرفر مباشرة وتطبيق شروط الاستثناء"""
        dfs = []
        for url in self.json_urls:
            try:
                # مكتبة Pandas قادرة على قراءة الـ JSON من الروابط مباشرة وبسرعة فائقة
                df_temp = pd.read_json(url, lines=True)
                dfs.append(df_temp)
            except Exception as e:
                print(f"تنبيه: تعذر جلب البيانات من الرابط {url}. الخطأ: {str(e)}")
                
        if not dfs:
            raise ValueError("لم يتم العثور على أي بيانات تاريخية من السيرفر.")
            
        df_hist = pd.concat(dfs, ignore_index=True)
        
        # التأكد من أنواع البيانات لضمان دقة العمليات الحسابية
        df_hist['contract_no'] = df_hist['contract_no'].astype(str)
        df_hist['type_of_customer'] = df_hist['type_of_customer'].astype(str)
        df_hist['cur_consump'] = pd.to_numeric(df_hist['cur_consump'], errors='coerce').fillna(0)
        df_hist['mult_factor'] = pd.to_numeric(df_hist['mult_factor'], errors='coerce').fillna(1)
        
        # تطبيق شرط الاستثناء (الفئات 35, 43, 335, 343 باستهلاك 200)
        exception_types = ['35', '43', '335', '343']
        condition_exception = (df_hist['type_of_customer'].isin(exception_types)) & (df_hist['cur_consump'] == 200)
        
        df_hist['historical_actual'] = np.where(
            condition_exception, 
            200, 
            df_hist['cur_consump'] * df_hist['mult_factor']
        )
        
        df_hist['period_date'] = pd.to_datetime(df_hist['period'], format='%m-%Y', errors='coerce')
        df_hist['month'] = df_hist['period_date'].dt.strftime('%m')
        
        return df_hist

    def extract_latest_status(self, df_hist):
        df_latest = df_hist.sort_values('period_date', ascending=False).drop_duplicates(subset=['contract_no'], keep='first')
        return df_latest[['contract_no', 'meter_status', 'connection_type', 'type_of_customer', 'mult_factor']]

    def calculate_historical_baseline(self, df_hist):
        df_same_month = df_hist[df_hist['month'] == self.current_month_str]
        df_valid_history = df_same_month[
            (df_same_month['meter_status'].astype(str) != '6') & 
            (df_same_month['connection_type'].astype(str) != '2')
        ]
        baseline = df_valid_history.groupby('contract_no')['historical_actual'].agg(
            hist_median='median',
            hist_mad=lambda x: np.median(np.abs(x - np.median(x)))
        ).reset_index()
        baseline['hist_mad'] = np.where(baseline['hist_mad'] == 0, 1.0, baseline['hist_mad'])
        return baseline

    def analyze_current_month(self):
        df_hist = self.load_historical_data()
        df_latest_status = self.extract_latest_status(df_hist)
        df_baseline = self.calculate_historical_baseline(df_hist)
        
        df_current = pd.read_excel(self.excel_path)
        col_map = {'رقم المشترك': 'contract_no', 'الاسم': 'customer_name', 'الحرف او المربع': 'area_block', 'الاستهلاك الشهري': 'current_consump'}
        df_current = df_current.rename(columns=col_map)
        df_current['contract_no'] = df_current['contract_no'].astype(str)
        df_current['current_consump'] = pd.to_numeric(df_current['current_consump'], errors='coerce').fillna(0)
        
        df_merged = df_current.merge(df_latest_status, on='contract_no', how='left')
        df_merged = df_merged.merge(df_baseline, on='contract_no', how='left')
        
        df_merged['meter_status'] = df_merged['meter_status'].fillna('2')
        df_merged['connection_type'] = df_merged['connection_type'].fillna('1')
        df_merged['mult_factor'] = df_merged['mult_factor'].fillna(1)
        
        exception_types = ['35', '43', '335', '343']
        cond_current_exc = (df_merged['type_of_customer'].isin(exception_types)) & (df_merged['current_consump'] == 200)
        df_merged['current_actual'] = np.where(cond_current_exc, 200, df_merged['current_consump'] * df_merged['mult_factor'])
        
        df_merged['z_score'] = (0.6745 * (df_merged['current_actual'] - df_merged['hist_median'])) / df_merged['hist_mad']
        df_merged['z_score'] = df_merged['z_score'].fillna(0).round(2)
        
        conditions = [
            (df_merged['connection_type'].astype(str) == '2'),
            (df_merged['meter_status'].astype(str) == '6'),
            (df_merged['hist_median'].isna()) & (df_merged['current_actual'] == 0),
            (df_merged['hist_median'].isna()) & (df_merged['current_actual'] > 0),
            (df_merged['hist_median'] > 0) & (df_merged['current_actual'] == 0),
            (df_merged['z_score'] > 2.5),
            (df_merged['z_score'] < -2.5) & (df_merged['current_actual'] > 0)
        ]
        
        choices = ['مستبعد - استهلاك ثابت', 'مستبعد - حساب موقوف', 'جديد - فترة تأسيس (استهلاك صفر)', 'جديد - تأسيس خط أساس (بداية استهلاك)', 'اشتباه عداد متوقف / عقار مغلق', 'قفزة غير منطقية (مراجعة الإدخال)', 'انخفاض حاد (اشتباه تلاعب)']
        df_merged['analysis_result'] = np.select(conditions, choices, default='طبيعي')
        
        final_columns = ['contract_no', 'customer_name', 'area_block', 'current_consump', 'current_actual', 'hist_median', 'z_score', 'analysis_result']
        return df_merged[final_columns]