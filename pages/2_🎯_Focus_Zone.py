# pages/2_🎯_Focus_Zone.py
import streamlit as st
import time

# --- FIX: Import the correctly named module from the 'core' directory ---
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core import gamification_utils

st.set_page_config(page_title="Focus Zone", page_icon="🎯")
st.title("🎯 The Focus Zone")
st.write("Complete your to-dos and use the focus timer to boost your productivity and level up!")

# Initialize state if not present
if 'todos' not in st.session_state:
    st.session_state.todos = []
if 'timer_running' not in st.session_state:
    st.session_state.timer_running = False
if 'duration_seconds' not in st.session_state:
    st.session_state.duration_seconds = 0

col1, col2 = st.columns(2)

# --- To-Do List Column ---
with col1:
    st.subheader("✅ Quick To-Do List")
    
    # Use a form to prevent the page from re-running on every keypress
    with st.form("todo_form", clear_on_submit=True):
        new_todo = st.text_input("Add a new to-do item:", key="new_todo_input", placeholder="e.g., Read Chapter 5")
        submitted = st.form_submit_button("Add Task")
        if submitted and new_todo:
            # Store todos as a list of dictionaries for more robust state
            st.session_state.todos.append({"task": new_todo, "id": f"todo_{len(st.session_state.todos)}"})
            st.rerun()

    if not st.session_state.todos:
        st.info("Your to-do list is empty. Add a task to get started!")
    else:
        # Iterate over a copy of the list to safely remove items
        for i, todo_item in enumerate(st.session_state.todos[:]):
            # The checkbox state is now independent of its label
            is_done = st.checkbox(todo_item["task"], key=todo_item["id"])
            if is_done:
                # Remove the completed item from the original list
                st.session_state.todos.pop(i)
                
                # --- FIX: Call the correctly named module ---
                # Award XP for completing the task
                st.session_state.todos_completed = st.session_state.get('todos_completed', 0) + 1
                feedback = gamification_utils.award_xp(gamification_utils.XP_PER_TODO_COMPLETED, "todo")
                
                st.toast(f"Great job! {feedback}", icon="🎉")
                time.sleep(1) # Give toast time to show before rerunning
                st.rerun()

# --- Focus Timer Column ---
with col2:
    st.subheader("⏳ Focus Timer (Pomodoro)")
    
    placeholder = st.empty()

    if not st.session_state.timer_running:
        with placeholder.container():
            duration_minutes = st.number_input(
                "Set focus duration (minutes):", min_value=5, max_value=120, value=25, step=5
            )
            if st.button("Start Focus Session", type="primary"):
                st.session_state.timer_running = True
                st.session_state.duration_seconds = duration_minutes * 60
                st.rerun()
    
    if st.session_state.timer_running:
        if st.button("Stop Timer"):
            st.session_state.timer_running = False
            st.session_state.duration_seconds = 0
            st.info("Timer stopped. Ready for the next session!")
            time.sleep(1)
            st.rerun()

        st.warning("Focus session in progress! Stay off your phone!")
        
        while st.session_state.duration_seconds > 0 and st.session_state.timer_running:
            mins, secs = divmod(st.session_state.duration_seconds, 60)
            timer_text = f"{mins:02d}:{secs:02d}"
            with placeholder.container():
                st.metric("Time Remaining", timer_text)
            time.sleep(1)
            # This check is important for the stop button to work instantly
            if st.session_state.timer_running:
                 st.session_state.duration_seconds -= 1

        if st.session_state.duration_seconds == 0 and st.session_state.timer_running:
            placeholder.empty()
            st.success("Focus session complete! Amazing work!")
            st.balloons()
            
            # --- FIX: Call the correctly named module ---
            st.session_state.focus_sessions_completed = st.session_state.get('focus_sessions_completed', 0) + 1
            feedback = gamification_utils.award_xp(gamification_utils.XP_PER_FOCUS_SESSION, "focus")
            st.info(feedback)
            
            st.session_state.timer_running = False
            time.sleep(2)
            st.rerun()