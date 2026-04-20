import streamlit as st
import requests
import pandas as pd
import io

# --- الإعدادات الأساسية ---
st.set_page_config(page_title="Trello Automation & Dashboard", layout="wide")

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
    "Mohamed Khamis": "Walid Altaher", "Abdel Aal": "Alaa Abd elaal",
    "Attia Kamal": "Attie Kamal", "Sherif Mohamed": "Sherif Mohamed",
    "Mahmoud Makhemar": "محمود مخيمر", "Ali Ramadan": "Ali Ramadan",
    "Mostafa Nubi": "Mustafa Noby", "Eslam Eid": "Eslam Eid",
    "Mohamed Mohamed": "Mohamed Bakry", "Ahmed Samy": "احمد سامي",
    "Ashraf Ahmed": "Ashraf Abo hamza19", "Ali Mohamed": "Ali Weza",
    "Mohamed Khattab": "mohmed hasn", "Hamdy A.Khalek": "Hamdi Kaled",
    "Essam Ahmed": "Kimo Kimo", "Ashraf Mohamed": "Tefa Abdellatif",
    "Amr Mohamed": "abuzeidamro8", "Ahmed Hussien": "احمد حسين",
    "Ahmed Amer": "Ahmad Amer", "Hassan Saleh": "Hassan Saleh",
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

trello = TrelloEngine(TRELLO_API_KEY, TRELLO_TOKEN)

st.title("📊 Trello-Adib & Takka Dashboard")

uploaded_file = st.file_uploader("ارفع ملف الإكسيل المحدث", type=["xlsx"])

if uploaded_file:
    # قراءة الملف
    df = pd.read_excel(uploaded_file, dtype={'Mobile': str})
    if 'Automation_Status' not in df.columns: 
        df['Automation_Status'] = 'Pending'

    # --- قسم الداش بورد الإحصائي ---
    st.subheader("📈 ملخص بيانات الملف")
    
    total_cards = len(df)
    adib_df = df[df['Product Name'].str.contains("Abu Dhabi Islamic Bank", na=False)]
    adib_count = len(adib_df)
    takka_count = total_cards - adib_count
    
    col1, col2, col3 = st.columns(3)
    col1.metric("إجمالي الحالات", total_cards)
    col2.metric("حالات ADIB", adib_count)
    col3.metric("حالات Takka", takka_count)

    st.divider()
    
    # توزيع المناديب في الملف
    if st.checkbox("إظهار تحليل توزيع المناديب"):
        st.bar_chart(df['Courier'].value_counts())
    
    st.divider()

    # --- بدء عملية المزامنة ---
    if st.button("🚀 بدء المزامنة مع تريلو", type="primary"):
        with st.spinner("جاري الاتصال بتريلو ومعالجة الكروت..."):
            cards_data = trello.get_data(f"boards/{BOARD_ID}/cards", {"fields": "name,idList,id"})
            lists_data = trello.get_data(f"boards/{BOARD_ID}/lists", {"fields": "name,id"})
            members_data = trello.get_data(f"boards/{BOARD_ID}/members", {"fields": "fullName,id"})
            labels_data = trello.get_data(f"boards/{BOARD_ID}/labels", {"fields": "name,id"})

            if lists_data and cards_data:
                list_map = {l['name'].strip(): l['id'] for l in lists_data}
                member_map = {m['fullName'].strip(): m['id'] for m in members_data}
                label_map = {lb.get('name','').strip(): lb['id'] for lb in labels_data}

                # إضافة شريط تقدم مرئي
                progress_bar = st.progress(0)
                status_text = st.empty()

                for index, row in df.iterrows():
                    # تحديث شريط التقدم
                    progress_val = (index + 1) / total_cards
                    progress_bar.progress(progress_val)
                    
                    if row['Automation_Status'] != 'Pending': continue

                    mobile = str(row['Mobile']).strip()
                    courier = str(row['Courier']).strip()
                    product = str(row['Product Name']).strip()
                    
                    prefix = "Adib" if "Abu Dhabi Islamic Bank" in product else "Takka"
                    source_list_id = list_map.get(prefix)

                    if not source_list_id: continue

                    for card in cards_data:
                        if card['idList'] == source_list_id and mobile in card['name']:
                            
                            # 1. إسناد المندوب (Assign) أو الليبل
                            if courier == "Mohamed Bakry":
                                if "Mohamed Bakry" in label_map:
                                    trello.add_to_card(card['id'], "label", label_map["Mohamed Bakry"])
                            else:
                                trello_name = NAME_MAP.get(courier)
                                if trello_name:
                                    m_id = member_map.get(trello_name.strip())
                                    if m_id: 
                                        trello.add_to_card(card['id'], "member", m_id)

                            # 2. تحديد قائمة النقل
                            target_list_name = f"{prefix} HC" if courier == "Hamdy A.Khalek" else f"{prefix} Assigned"

                            # 3. تنفيذ النقل
                            if target_list_name in list_map:
                                trello.update_card(card['id'], {"idList": list_map[target_list_name]})
                                df.at[index, 'Automation_Status'] = 'Done'
                                st.write(f"✅ تم نقل: {row['Name']} -> {target_list_name} ({courier})")

                # تصدير ملف النتائج بعد المزامنة
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                
                st.success("🏁 تم الانتهاء من جميع الكروت!")
                st.download_button("📥 تحميل تقرير العمل النهائي", output.getvalue(), "Trello_Status_Report.xlsx")
            else:
                st.error("🛑 فشل في جلب البيانات من تريلو. تأكد من إعدادات الـ Secrets.")
