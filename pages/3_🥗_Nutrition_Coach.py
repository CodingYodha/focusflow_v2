# pages/3_🥗_Nutrition_Coach.py
import streamlit as st
import google.generativeai as genai

st.set_page_config(page_title="Nutrition Coach", page_icon="🥗")
st.title("🥗 AI Nutrition Coach")

# Ensure user is onboarded
if "user_profile" not in st.session_state or st.session_state.user_profile is None:
    st.warning("Please complete your profile on the main 'FocusFlow - Chat' page first.")
    st.stop()

# Initialize session state for this page
if "meal_plan" not in st.session_state:
    st.session_state.meal_plan = ""
if "shopping_list" not in st.session_state:
    st.session_state.shopping_list = ""

with st.form("nutrition_form"):
    st.write(f"Hello {st.session_state.user_profile['name']}! Let's create a meal plan for you.")
    
    goal = st.selectbox(
        "What is your primary wellness goal?",
        ("Improve Energy & Focus", "Build Muscle", "Weight Loss", "Healthy Skin")
    )
    
    dietary_prefs = st.multiselect(
        "Do you have any dietary preferences or restrictions?",
        ["Vegetarian", "Vegan", "Gluten-Free", "Dairy-Free", "Low-Carb"]
    )
    
    cuisine_style = st.text_input("Any preferred cuisine style? (e.g., Indian, Italian, leave blank for any)")
    
    submitted = st.form_submit_button("Generate My Meal Plan", type="primary")

if submitted:
    st.session_state.shopping_list = "" # Reset shopping list
    with st.spinner("Crafting your personalized meal plan... This may take a moment."):
        try:
            genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            
            # Construct a detailed prompt for the AI
            prompt = f"""
            As an expert nutritionist, create a simple, healthy, and budget-friendly one-day meal plan for a student named {st.session_state.user_profile['name']}.

            **Student's Goal:** {goal}
            **Dietary Preferences/Restrictions:** {', '.join(dietary_prefs) or 'None'}
            **Preferred Cuisine:** {cuisine_style or 'Any'}

            **Instructions:**
            1.  The plan should be easy for a busy student to prepare.
            2.  Provide three main meals (Breakfast, Lunch, Dinner) and one snack.
            3.  For each meal, provide a simple name, a short list of ingredients, and 1-2 sentences of simple preparation instructions.
            4.  Format the entire output as clean Markdown. Use headings for each meal.
            """
            
            response = model.generate_content(prompt)
            st.session_state.meal_plan = response.text
        except Exception as e:
            st.error(f"Failed to generate meal plan: {e}")

if st.session_state.meal_plan:
    st.subheader("Your Personalized Meal Plan")
    st.markdown(st.session_state.meal_plan)
    
    st.divider()
    
    # Agentic Step: Generate Shopping List
    if st.button("🛒 Generate Shopping List"):
        with st.spinner("Creating your shopping list..."):
            try:
                model = genai.GenerativeModel('gemini-1.5-flash-latest')
                prompt = f"""
                From the following meal plan, extract all unique ingredients and format them as a simple Markdown checklist. Group them into categories like 'Produce', 'Protein', 'Pantry', and 'Dairy'.

                **Meal Plan:**
                {st.session_state.meal_plan}
                """
                response = model.generate_content(prompt)
                st.session_state.shopping_list = response.text
            except Exception as e:
                st.error(f"Failed to generate shopping list: {e}")

if st.session_state.shopping_list:
    st.subheader("🛒 Your Shopping List")
    st.markdown(st.session_state.shopping_list)