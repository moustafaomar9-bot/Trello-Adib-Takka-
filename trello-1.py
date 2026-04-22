import streamlit as st
import requests
import pandas as pd
import io
import plotly.express as px
from datetime import datetime

# --- الإعدادات الأساسية ---
st.set_page_config(page_title="Trello Automation Pro", layout="wide")

# --- جلب البيانات الحساسة من Secrets ---
try:
    TRELLO_API_KEY = st.secrets["TRELLO_API_KEY"]
    TRELLO_TOKEN = st.secrets["TRELLO_TOKEN"]
    BOARD_ID = st.secrets["BOARD_ID"]
except KeyError:
    st.error("🛑 لم يتم العثور على المفاتيح في Secrets. يرجى إضافتها في إعدادات Streamlit Cloud.")
    st.stop()

# خريطة المناديب (الاسم في الإكسيل : الاسم في تريلو)
NAME_MAP = {
    "Mohamed Khamis": "Walid Altaher", "Abdel Aaal": "Alaa Abd elaal",
    "Attia Kamal": "Attie Kamal", "Sherif Mohamed": "Sherif Mohamed",
    "Mahmoud Makhemar": "محمود مخيمر", "Ali Ramadan": "Ali Ramadan",
    "Mostafa Nubi": "Mustafa Noby", "Eslam Eid": "Eslam Eid",
    "Mohamed Mohamed": "Mohamed Bakry", "Ahmed Samy": "احمد سامي",
    "Ashraf Ahmed": "Ashraf Abo Hamza19", "Ali Mohamed": "Ali Weza",
    "Mohamed Khattab": "mohmed hasn", "Hamdy A.Khalek": "Hamdi Kaled",
    "Essam Ahmed": "Kimo Kimo", "Ashraf Mohamed": "Tefa Abdellatif",
    "Amr Mohamed": "abuzeidamro8", "Ahmed Hussien": "احمد حسين",
    "Ahmed Amer": "Ahmad Amer", "Hassan Saleh": "Hasan Saleh",
    "Ibrahim Azmy": "ابراهيم عزمي", "Sief Samy": "Sefi Jamica"
}

class TrelloEngine:
    def __init__(self, api_key, token):
        self.params = {"key": api_key, "token": token}
        self.base_url = "https://api.trello.com/1"

    def get_data(self, endpoint, extra_params=None):
        request_params = self.params.copy()
        if extra_params: request_params.update(extra_params)
        response = requests.get(f"{self.base_url}/{endpoint}", params=request_params)
        return response.json() if response.status_code == 200 else None

    def update_card(self, card_id, payload):
        return requests.put(f"{self.base_url}/cards/{card_id}", params=self.params, json=payload)

    def add_to_card(self, card_id, item_type, item_id):
        field = "idMembers" if item_type == "member" else "idLabels"
        return requests.post(f"{self.base_url}/cards/{card_id}/{field}", params={**self.params, "value": item_id})

    def remove_from_card(self, card_id, item_type, item_id):
        field = "idMembers" if item_type == "member" else "idLabels"
        return requests.delete(f"{self.base_url}/cards/{card_id}/{field}/{item_id}", params=self.params)

trello = TrelloEngine(TRELLO_API_KEY, TRELLO_TOKEN)

st.title("📊 Trello Automation (Primary + Extended Search)")

uploaded_file = st.file_uploader("ارفع ملف الإكسيل المحدث", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file, dtype={'Mobile': str})
    if 'Automation_Status' not in df.columns: 
        df['Automation_Status'] = 'Pending'

    is_adib = df['Product Name'].str.contains("Abu Dhabi Islamic Bank", na=False, case=False)
    is_takka = df['Product Name'].str.contains("Takka", na=False, case=False)
    is_other = ~(is_adib | is_takka)

    if st.button("🚀 بدء المزامنة الذكية", type="primary"):
        with st.spinner("جاري فحص القوائم والمعالجة..."):
            cards_data = trello.get_data(f"boards/{BOARD_ID}/cards", {"fields": "name,idList,id,idMembers,idLabels"})
            lists_data = trello.get_data(f"boards/{BOARD_ID}/lists", {"fields": "name,id"})
            members_data = trello.get_data(f"boards/{BOARD_ID}/members", {"fields": "fullName,id"})
            labels_data = trello.get_data(f"boards/{BOARD_ID}/labels", {"fields": "name,id"})

            if lists_data and cards_data:
                list_map = {l['name'].strip(): l['id'] for l in lists_data}
                member_map = {m['fullName'].strip(): m['id'] for m in members_data}
                label_map = {lb.get('name','').strip(): lb['id'] for lb in labels_data}

                today_date = datetime.now().isoformat()
                progress_bar = st.progress(0)
                
                for index, row in df.iterrows():
                    progress_bar.progress((index + 1) / len(df))
                    if is_other[index] or row['Automation_Status'] != 'Pending': continue

                    mobile = str(row['Mobile']).strip()
                    courier = str(row['Courier']).strip()
                    prefix = "Adib" if is_adib[index] else "Takka"
                    
                    # 1. تحديد الليست الأساسية
                    primary_list_id = list_map.get(prefix)
                    
                    # 2. تحديد الليستات الإضافية للبحث
                    other_list_names = [
                        f"{prefix} Assigned", f"Done ({prefix})", 
                        f"No Answer {prefix}", f"{prefix} HC"
                    ]
                    other_list_ids = [list_map.get(name) for name in other_list_names if list_map.get(name)]

                    for card in cards_data:
                        found_in_primary = (card['idList'] == primary_list_id)
                        found_in_others = (card['idList'] in other_list_ids)

                        if (found_in_primary or found_in_others) and mobile in card['name']:
                            
                            # --- منطق التنظيف (فقط لو الكارت في الليستات الإضافية/القديمة) ---
                            if found_in_others:
                                for m_id in card.get('idMembers', []):
                                    trello.remove_from_card(card['id'], "member", m_id)
                                for l_id in card.get('idLabels', []):
                                    trello.remove_from_card(card['id'], "label", l_id)

                            # --- منطق الإسناد الجديد ---
                            assign_success = False
                            if courier == "Mohamed Bakry":
                                if "Mohamed Bakry" in label_map:
                                    trello.add_to_card(card['id'], "label", label_map["Mohamed Bakry"])
                                    assign_success = True
                            else:
                                trello_name = NAME_MAP.get(courier)
                                if trello_name:
                                    m_id = member_map.get(trello_name.strip())
                                    if m_id: 
                                        trello.add_to_card(card['id'], "member", m_id)
                                        assign_success = True

                            # --- النقل وتحديث الحالة ---
                            if assign_success:
                                target_list_name = f"{prefix} HC" if courier == "Hamdy A.Khalek" else f"{prefix} Assigned"
                                if target_list_name in list_map:
                                    payload = {"idList": list_map[target_list_name]}
                                    
                                    # تحديث التاريخ فقط إذا كان الكارت قادماً من القوائم الإضافية
                                    if found_in_others:
                                        payload["due"] = today_date
                                    
                                    trello.update_card(card['id'], payload)
                                    df.at[index, 'Automation_Status'] = 'Done'
                                    status_msg = "تحديث حالة قديمة" if found_in_others else "إسناد جديد"
                                    st.write(f"✅ {status_msg}: {row['Name']} ({prefix})")
                                    break 
                            else:
                                df.at[index, 'Automation_Status'] = 'Failed: Courier Not Found'
                                st.error(f"⚠️ {row['Name']}: المندوب غير موجود في NAME_MAP.")
                                break

                st.success("🏁 اكتملت المعالجة بنجاح!")
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                st.download_button("📥 تحميل التقرير النهائي", output.getvalue(), "Trello_Final_Report.xlsx")
            else:
                st.error("🛑 فشل في الاتصال بتريلو أو جلب القوائم.")
