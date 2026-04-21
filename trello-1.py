import streamlit as st
import requests
import pandas as pd
import io
import plotly.express as px

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

trello = TrelloEngine(TRELLO_API_KEY, TRELLO_TOKEN)

st.title("📊 Trello-Adib & Takka Dashboard")

uploaded_file = st.file_uploader("ارفع ملف الإكسيل المحدث", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file, dtype={'Mobile': str})
    if 'Automation_Status' not in df.columns: 
        df['Automation_Status'] = 'Pending'

    # --- تحسين منطق الفلترة لضمان الدقة ---
    is_adib = df['Product Name'].str.contains("Abu Dhabi Islamic Bank", na=False, case=False)
    is_takka = df['Product Name'].str.contains("Takka", na=False, case=False)
    is_other = ~(is_adib | is_takka)

    st.subheader("📈 ملخص بيانات الملف (دقيق)")
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric("إجمالي الشيت", len(df))
    col2.metric("حالات ADIB", is_adib.sum())
    col3.metric("حالات Takka", is_takka.sum())
    col4.metric("حالات أخرى (تجاهل)", is_other.sum(), delta_color="normal")

    st.divider()
    
    if st.checkbox("إظهار تحليل توزيع المناديب (بالأرقام)"):
        target_df = df[is_adib | is_takka]
        if not target_df.empty:
            counts = target_df['Courier'].value_counts().reset_index()
            counts.columns = ['المندوب', 'عدد الحالات']
            
            fig = px.bar(
                counts, 
                x='المندوب', 
                y='عدد الحالات',
                text='عدد الحالات',
                title="توزيع الحالات على المناديب",
                color='عدد الحالات',
                color_continuous_scale='Blues'
            )
            fig.update_traces(textposition='outside')
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("لا توجد حالات لأديب أو تكة لعرضها.")
    
    st.divider()

    if st.button("🚀 بدء المزامنة الآمنة (نقل عند نجاح الإسناد فقط)", type="primary"):
        with st.spinner("جاري الاتصال بتريلو ومعالجة الكروت..."):
            cards_data = trello.get_data(f"boards/{BOARD_ID}/cards", {"fields": "name,idList,id"})
            lists_data = trello.get_data(f"boards/{BOARD_ID}/lists", {"fields": "name,id"})
            members_data = trello.get_data(f"boards/{BOARD_ID}/members", {"fields": "fullName,id"})
            labels_data = trello.get_data(f"boards/{BOARD_ID}/labels", {"fields": "name,id"})

            if lists_data and cards_data:
                list_map = {l['name'].strip(): l['id'] for l in lists_data}
                member_map = {m['fullName'].strip(): m['id'] for m in members_data}
                label_map = {lb.get('name','').strip(): lb['id'] for lb in labels_data}

                progress_bar = st.progress(0)
                
                for index, row in df.iterrows():
                    progress_bar.progress((index + 1) / len(df))
                    
                    if is_other[index] or row['Automation_Status'] != 'Pending':
                        continue

                    mobile = str(row['Mobile']).strip()
                    courier = str(row['Courier']).strip()
                    product = str(row['Product Name']).strip()
                    
                    prefix = "Adib" if is_adib[index] else "Takka"
                    source_list_id = list_map.get(prefix)

                    if not source_list_id: continue

                    for card in cards_data:
                        if card['idList'] == source_list_id and mobile in card['name']:
                            
                            # --- منطق الإسناد المشروط (الأمان الجديد) ---
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

                            # --- النقل يحدث فقط إذا تم الإسناد بنجاح ---
                            if assign_success:
                                target_list_name = f"{prefix} HC" if courier == "Hamdy A.Khalek" else f"{prefix} Assigned"
                                if target_list_name in list_map:
                                    trello.update_card(card['id'], {"idList": list_map[target_list_name]})
                                    df.at[index, 'Automation_Status'] = 'Done'
                                    st.write(f"✅ تم إسناد ونقل: {row['Name']} ({prefix})")
                            else:
                                df.at[index, 'Automation_Status'] = 'Failed: Courier Not Found'
                                st.error(f"⚠️ لم يتم نقل {row['Name']}: المندوب '{courier}' غير موجود في خريطة المناديب.")

                st.success("🏁 اكتملت المزامنة!")
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                st.download_button("📥 تحميل التقرير النهائي", output.getvalue(), "Trello_Status_Report.xlsx")
            else:
                st.error("🛑 فشل في الاتصال بتريلو.")
