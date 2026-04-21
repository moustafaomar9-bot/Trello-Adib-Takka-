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

st.title("📊 Trello Smart Automation (Multi-List Mode)")

uploaded_file = st.file_uploader("ارفع ملف الإكسيل المحدث", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file, dtype={'Mobile': str})
    if 'Automation_Status' not in df.columns: 
        df['Automation_Status'] = 'Pending'

    # --- فلترة المشاريع المطلوبة ---
    is_adib = df['Product Name'].str.contains("Abu Dhabi Islamic Bank", na=False, case=False)
    is_takka = df['Product Name'].str.contains("Takka", na=False, case=False)
    is_other = ~(is_adib | is_takka)

    st.subheader("📈 ملخص البيانات")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("إجمالي الشيت", len(df))
    col2.metric("حالات ADIB", is_adib.sum())
    col3.metric("حالات Takka", is_takka.sum())
    col4.metric("تجاهل", is_other.sum())

    st.divider()

    if st.button("🚀 بدء المزامنة الشاملة (البحث في كل القوائم)", type="primary"):
        with st.spinner("جاري فحص جميع قوائم تريلو..."):
            cards_data = trello.get_data(f"boards/{BOARD_ID}/cards", {"fields": "name,idList,id,idMembers,idLabels"})
            lists_data = trello.get_data(f"boards/{BOARD_ID}/lists", {"fields": "name,id"})
            members_data = trello.get_data(f"boards/{BOARD_ID}/members", {"fields": "fullName,id"})
            labels_data = trello.get_data(f"boards/{BOARD_ID}/labels", {"fields": "name,id"})

            if lists_data and cards_data:
                list_map = {l['name'].strip(): l['id'] for l in lists_data}
                member_map = {m['fullName'].strip(): m['id'] for m in members_data}
                label_map = {lb.get('name','').strip(): lb['id'] for lb in labels_data}

                # تحديد نطاق البحث لكل مشروع
                adib_search_scopes = ["Adib", "Adib Assigned", "Done (Adib)", "No Answer Adib", "Adib HC"]
                takka_search_scopes = ["Takka", "Takka Assigned", "Done (Takka)", "No Answer Takka", "Takka HC"]
                
                adib_list_ids = [list_map[n] for n in adib_search_scopes if n in list_map]
                takka_list_ids = [list_map[n] for n in takka_search_scopes if n in list_map]

                today_date = datetime.now().isoformat()
                progress_bar = st.progress(0)
                
                for index, row in df.iterrows():
                    progress_bar.progress((index + 1) / len(df))
                    if is_other[index] or row['Automation_Status'] != 'Pending': continue

                    mobile = str(row['Mobile']).strip()
                    courier = str(row['Courier']).strip()
                    prefix = "Adib" if is_adib[index] else "Takka"
                    current_scope = adib_list_ids if prefix == "Adib" else takka_list_ids

                    for card in cards_data:
                        # البحث في نطاق القوائم المحددة للمشروع
                        if card['idList'] in current_scope and mobile in card['name']:
                            
                            # 1. إزالة المندوب والليبل القديم (Clean Slate)
                            for m_id in card.get('idMembers', []):
                                trello.remove_from_card(card['id'], "member", m_id)
                            for l_id in card.get('idLabels', []):
                                trello.remove_from_card(card['id'], "label", l_id)

                            # 2. محاولة إسناد المندوب الجديد
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

                            # 3. النقل وتحديث التاريخ
                            if assign_success:
                                target_list_name = f"{prefix} HC" if courier == "Hamdy A.Khalek" else f"{prefix} Assigned"
                                if target_list_name in list_map:
                                    trello.update_card(card['id'], {
                                        "idList": list_map[target_list_name],
                                        "due": today_date # تحديث التاريخ لليوم
                                    })
                                    df.at[index, 'Automation_Status'] = 'Done'
                                    st.write(f"🔄 تم تحديث ونقل: {row['Name']} ({prefix})")
                            else:
                                df.at[index, 'Automation_Status'] = 'Failed: Courier Not Found'
                                st.error(f"⚠️ {row['Name']}: المندوب '{courier}' غير موجود.")

                st.success("🏁 اكتملت المزامنة الذكية!")
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                st.download_button("📥 تحميل التقرير النهائي", output.getvalue(), "Trello_Smart_Report.xlsx")
            else:
                st.error("🛑 فشل في الاتصال بتريلو.")
