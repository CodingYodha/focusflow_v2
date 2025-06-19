# pages/2_🎯_Focus_Zone.py
import streamlit as st
import time

# Import utilities from the main app directory
import sys
sys.path.append('..')
import gamification

st.set_page_config(page_title="Focus Zone", page_icon="🎯")
# Initialize state if not present
if 'todos' not in st.session_state:
    st.session_state.todos = []
if 'timer_running' not in st.session_state:
    st.session_state.timer_running = False
st.title("🎯 The Focus Zone")
st.write("Complete your to-dos and use the focus timer to boost your productivity and level up!")


col1, col2 = st.columns(2)

# --- To-Do List Column ---
with col1:
    st.subheader("✅ Quick To-Do List")
    
    new_todo = st.text_input("Add a new to-do item:", key="new_todo_input")
    if st.button("Add Task") and new_todo:
        st.session_state.todos.append(new_todo)
        st.rerun()

    if not st.session_state.todos:
        st.info("Your to-do list is empty. Add a task to get started!")
    else:
        # Create a copy to iterate over, so we can modify the original list
        for todo in st.session_state.todos[:]:
            if st.checkbox(todo, key=f"todo_{todo}"):
                st.session_state.todos.remove(todo)
                st.session_state.todos_completed += 1
                feedback = gamification.award_xp(gamification.XP_PER_TODO_COMPLETED, "todo")
                st.toast(f"Great job! {feedback}", icon="🎉")
                time.sleep(1) # Give toast time to show
                st.rerun()

# --- Focus Timer Column ---
with col2:
    st.subheader("⏳ Focus Timer (Pomodoro)")

    if st.session_state.timer_running:
        st.warning("Timer is currently running! Stay focused!")
    else:
        duration_minutes = st.number_input(
            "Set focus duration (minutes):", min_value=5, max_value=120, value=25, step=5
        )

    if st.button("Start Focus Session", disabled=st.session_state.timer_running):
        st.session_state.timer_running = True
        st.session_state.duration_seconds = duration_minutes * 60
        
        placeholder = st.empty()
        st.warning("Focus session started! Minimize distractions.")
        
        while st.session_state.duration_seconds > 0:
            mins, secs = divmod(st.session_state.duration_seconds, 60)
            timer_text = f"{mins:02d}:{secs:02d}"
            with placeholder.container():
                st.metric("Time Remaining", timer_text)
            time.sleep(1)
            st.session_state.duration_seconds -= 1

        placeholder.empty()
        st.success("Focus session complete! Well done!")
        st.balloons()
        st.session_state.focus_sessions_completed += 1
        feedback = gamification.award_xp(gamification.XP_PER_FOCUS_SESSION, "focus")
        st.info(feedback)
        
        st.session_state.timer_running = False
        time.sleep(2) # Give user time to see message
        st.rerun()