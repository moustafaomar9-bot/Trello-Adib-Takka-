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
    st.error("🛑 لم يتم العثور على المفاتيح في Secrets.")
    st.stop()

# خريطة المناديب
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

st.title("📊 Trello Smart Automation & Dashboard")

uploaded_file = st.file_uploader("ارفع ملف الإكسيل المحدث", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file, dtype={'Mobile': str})
    if 'Automation_Status' not in df.columns: 
        df['Automation_Status'] = 'Pending'

    is_adib = df['Product Name'].str.contains("Abu Dhabi Islamic Bank", na=False, case=False)
    is_takka = df['Product Name'].str.contains("Takka", na=False, case=False)
    is_other = ~(is_adib | is_takka)

    # --- الداشبورد ---
    st.subheader("📈 ملخص البيانات")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("إجمالي الملف", len(df))
    c2.metric("ADIB", is_adib.sum())
    c3.metric("Takka", is_takka.sum())
    c4.metric("تجاهل", is_other.sum())

    if st.checkbox("إظهار توزيع المناديب"):
        counts = df[is_adib | is_takka]['Courier'].value_counts().reset_index()
        counts.columns = ['المندوب', 'الحالات']
        st.plotly_chart(px.bar(counts, x='المندوب', y='الحالات', text='الحالات', color='الحالات'), use_container_width=True)

    st.divider()

    if st.button("🚀 بدء المزامنة الذكية", type="primary"):
        with st.spinner("جاري معالجة البيانات..."):
            cards_data = trello.get_data(f"boards/{BOARD_ID}/cards", {"fields": "name,idList,id,idMembers,idLabels,due"})
            lists_data = trello.get_data(f"boards/{BOARD_ID}/lists", {"fields": "name,id"})
            members_data = trello.get_data(f"boards/{BOARD_ID}/members", {"fields": "fullName,id"})
            labels_data = trello.get_data(f"boards/{BOARD_ID}/labels", {"fields": "name,id"})

            if lists_data and cards_data:
                list_map = {l['name'].strip(): l['id'] for l in lists_data}
                member_map = {m['fullName'].strip(): m['id'] for m in members_data}
                label_map = {lb.get('name','').strip(): lb['id'] for lb in labels_data}
                hajar_id = next((m['id'] for m in members_data if "Hajar Mostafa" in m['fullName']), None)

                today_date_str = datetime.now().strftime('%Y-%m-%d')
                today_iso = datetime.now().date().isoformat()
                progress_bar = st.progress(0)
                
                for index, row in df.iterrows():
                    progress_bar.progress((index + 1) / len(df))
                    if is_other[index] or row['Automation_Status'] != 'Pending': continue

                    mobile = str(row['Mobile']).strip()
                    courier = str(row['Courier']).strip()
                    prefix = "Adib" if is_adib[index] else "Takka"
                    
                    primary_list_id = list_map.get(prefix)
                    target_list_name = f"{prefix} HC" if courier == "Hamdy A.Khalek" else f"{prefix} Assigned"
                    target_list_id = list_map.get(target_list_name)

                    other_list_names = [f"{prefix} Assigned", f"Done ({prefix})", f"No Answer {prefix}", f"{prefix} HC"]
                    other_list_ids = [list_map.get(n) for n in other_list_names if list_map.get(n)]

                    for card in cards_data:
                        if mobile in card['name']:
                            in_primary = (card['idList'] == primary_list_id)
                            in_others = (card['idList'] in other_list_ids)

                            if in_primary:
                                # --- منطق الليست الأساسية: إسناد ونقل مباشر ---
                                assign_ok = False
                                if courier == "Mohamed Bakry" and "Mohamed Bakry" in label_map:
                                    trello.add_to_card(card['id'], "label", label_map["Mohamed Bakry"])
                                    assign_ok = True
                                else:
                                    m_id = member_map.get(NAME_MAP.get(courier))
                                    if m_id:
                                        trello.add_to_card(card['id'], "member", m_id)
                                        assign_ok = True
                                
                                if assign_ok:
                                    trello.update_card(card['id'], {"idList": target_list_id})
                                    df.at[index, 'Automation_Status'] = 'Done (New)'
                                    st.write(f"🆕 كارت جديد: {row['Name']}")
                                break

                            elif in_others:
                                # --- منطق باقي القوائم: التدقيق والتحديث ---
                                card_due = card.get('due', '')[:10] if card.get('due') else ""
                                t_name = NAME_MAP.get(courier)
                                t_member_id = member_map.get(t_name) if t_name else None
                                
                                is_correct_member = (t_member_id in card.get('idMembers', [])) if t_member_id else False
                                if courier == "Mohamed Bakry":
                                    is_correct_member = label_map.get("Mohamed Bakry") in card.get('idLabels', [])
                                
                                # الشرط: لو كل شيء صح (مندوب + لستة + تاريخ) -> تجاهل
                                if is_correct_member and (card['idList'] == target_list_id) and (card_due == today_date_str):
                                    df.at[index, 'Automation_Status'] = 'Already Correct'
                                    break
                                
                                # تنفيذ التحديث للمرتجعات
                                for m_id in card.get('idMembers', []):
                                    if m_id != hajar_id: trello.remove_from_card(card['id'], "member", m_id)
                                for l_id in card.get('idLabels', []):
                                    trello.remove_from_card(card['id'], "label", l_id)

                                assign_ok = False
                                if courier == "Mohamed Bakry" and "Mohamed Bakry" in label_map:
                                    trello.add_to_card(card['id'], "label", label_map["Mohamed Bakry"])
                                    assign_ok = True
                                elif t_member_id:
                                    trello.add_to_card(card['id'], "member", t_member_id)
                                    assign_ok = True
                                
                                if assign_ok:
                                    trello.update_card(card['id'], {"idList": target_list_id, "due": today_iso})
                                    df.at[index, 'Automation_Status'] = 'Updated (Return)'
                                    st.write(f"🔄 تحديث مرتجع: {row['Name']}")
                                break

                st.success("🏁 اكتملت المزامنة!")
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                st.download_button("📥 تحميل التقرير", output.getvalue(), "Trello_Status_Report.xlsx")
