from groq import Groq
import streamlit as st
import os
import tempfile
from crewai import Crew, Agent, Task, Process
import json
import os
import requests
from crewai_tools import tool
from crewai import Crew, Process
import tomllib
from langchain_groq import ChatGroq
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection


# create title for the streamlit app

st.title('Autonomous Customer Interviewer')

# create a description

st.write(f"""This app is designed to help you conduct customer interviews. It uses the Llama 3 model on Groq to generate questions, 
         execute the interview and summarize the interview. For more information, contact Dries Faems at https://www.linkedin.com/in/dries-faems-0371569/""")

# ask user to input access code

# read excell file Access

access = st.text_input('Please enter your WHU email address').lower()

# Establish connection to Google Sheet
conn = st.connection("gsheets", type=GSheetsConnection)

# Read existing data from the sheet
data = conn.read(worksheet = "Sheet1", ttl=0)
accessdata = conn.read(worksheet = "Sheet2")

# check if the access code is correct

accesslist = accessdata['Email'].tolist()

if len(access) == 0:
    st.write('')
elif access not in accesslist:
    st.write('Access code invalid; Please enter the correct WHU email address')
else:
    # create a text input for the user to input the name of the customer

    groq_api_key = st.text_input('Please provide your Groq API Key. You can get a free API key at https://console.groq.com/playground', type="password")

    painpoint = st.text_input('What is the painpoint, which you want to explore in the interview?')
    customer_pofile = st.text_input('What is the profile of the customer you want to interview?')
    prior_learnings = st.text_input('What have you learned so far about the painpoint?')
    
    if st.button('Start Interview'):
        
        # Create a new record as a DataFrame
        new_record = pd.DataFrame({
            'Timestamp': [datetime.datetime.now()],
            'User': [access],
            'Action': ['Clicked on Start Interview'],
            'Painpoint': [painpoint],
            'Customer_Profile': [customer_pofile]
        })

        # add new record to the DataFrame

        updated_data = pd.concat([data, new_record], ignore_index=True)

        # Write the updated data back to the Google Sheet
        
        conn.update(worksheet = "Sheet1", data=updated_data)
        
        os.environ["GROQ_API_KEY"] = groq_api_key
        client = Groq()
        GROQ_LLM = ChatGroq(
                # api_key=os.getenv("GROQ_API_KEY"),
                model="llama3-70b-8192"
            )
        interview_question_generator = Agent(
            role='Generating interview questions',
            goal=f"""Prepare a list of interview questions to ask a specific customer profile about a specific painpoint.""", 
            backstory=f"""You are a great expert in generating interview questions to better understand the painpoints for a specific customer profile. You will prepare a list of questions to ask a specific customer about the provided painpoint
            Typical examples of questions are: (i) What is the hardest part of the job_to_be_done, (ii) When did you face this hardes part for the last time, (iii) What did you do to overcome this problem, (iv) What would you like to see improved in the future?. Based on your great experience, please think about additional questions that would be relevant to ask to better understand the pain points.
            Here are some specific guidelines to take into account for executing an excellent customer interview: (1) It is about getting information instead of confirmation, (2) A customer interview is not a sales pitch,
            (3) Ask questions about the past instead of the future, (4) Phrases such as 'could you' of 'would you'should be avoided, (5) Ask for specific examples""",
            verbose=True,
            llm=GROQ_LLM,
            allow_delegation=False,
            max_iter=5,
            memory=True,
        )

        customer_interviewer = Agent(
            role='Executing customer interviews',
            goal=f"""Conduct semi-structured customer interviews starting from the questions that are prepared by the interview question generator.""",
            backstory="""You are a great expert in conducting interviews with customers to better understand the painpoitns for a specific customer.
            You rely on the questions that are generated by the interview question generator. You can probe for additional questions to get a deep understanding of the underlying 
            pain points.  Here are some specific guidelines to take into account for executing an excellent customer interview: (1) It is about getting information instead of confirmation, (2) A customer interview is not a sales pitch,
            (3) Ask questions about the past instead of the future, (4) Phrases such as 'could you' of 'would you'should be avoided, (5) Ask for specific examples.""",
            verbose=True,
            llm=GROQ_LLM,
            allow_delegation=False,
            max_iter=5,
            memory=True,
        )

        interview_analyzer = Agent(
            role='Analyzing customer interviews',
            goal=f"""Analyze the customer interviews to identify the most important observations regarding the painpoints for the specific customer.""",
            backstory="""You are a great expert in analyzing customer interviews to identify what we can learn about the painpoint based on the interview. The learnings should
            help the user to better understand the exact nature of the painpoint. Your main expertise is on educating the user in what can be learned from the interview""",
            verbose=True,
            llm=GROQ_LLM,
            allow_delegation=False,
            max_iter=5,
            memory=True,
        )

        learnings_updater = Agent(
            role='Updating learnings',
            goal=f"""Update the learnings about the painpoint based on the learnings of the interview_analyzer.""",
            backstory="""You are a great expert in updating the learnings about the painpoint based on the learnings of the interview_analyzer. 
            You will update the learnings based on the most important observations that are identified by the interview_analyzer""",
            verbose=True,
            llm=GROQ_LLM,
            allow_delegation=False,
            max_iter=5,
            memory=True,
        )
        
        # Create tasks for the agents
        generate_interview_questions = Task(
            description=f"""Generate interview questions to ask customers about the following painpoint: {painpoint}. Here is a description of the customer profile: {customer_pofile}""",
            expected_output='As output, you provide a list of interview questions that can be used for the customer interview.',
            agent=interview_question_generator
        )

        interview_customer = Task(
            description=f"""Interview the customer to identify painpoints about the following painpoint: {painpoint}. Here is a description of the customer profile:
            {customer_pofile}. It is important to rely on the questions generated by the interview_question_generator.""",
            expected_output="""As output, you provide an exhaustive transcript of the interview.""",
            agent=customer_interviewer
        )

        analyze_interview = Task(
            description=f"""Analyze the customer interview that is executed by the customer_interviewer to generate learnings about the painpoint. 
            Help the user in leveraging the interview to get a better understanding of the painpoint. When analyzing the interview, make sure to focus on aspects such as (i) when does the customer face the pain point, (ii) what is the hardes part about the painpoint, (iii) why is the customer not able to solve the painpoint""",
            expected_output='As output, you provide an overview of the most important learnings.',
            agent=interview_analyzer
        )

        update_learnings = Task(
            description=f"""Update the learnings about the painpoint based on the learnings of the interview_analyzer. Here is a description of the prior learnings: {prior_learnings}""",
            expected_output='As output, you provide an updated version of the learnings about the painpoint. Make sure to combine the prior learnings with the new learnings and provide one single integrated overview.',
            agent=learnings_updater
        )

        # Instantiate the crew with a sequential process
        if prior_learnings == '':
            crew = Crew(
                agents=[interview_question_generator, customer_interviewer, interview_analyzer],
                tasks=[generate_interview_questions, interview_customer, analyze_interview],
                process=Process.sequential,
                full_output=True,
                share_crew=False,
            )
            results = crew.kickoff()
            st.write(generate_interview_questions.output.raw_output)
            st.write(interview_customer.output.raw_output)
            st.write(analyze_interview.output.raw_output)

        else:
            crew = Crew(
                agents=[interview_question_generator, customer_interviewer, interview_analyzer, learnings_updater],
                tasks=[generate_interview_questions, interview_customer, analyze_interview, update_learnings],
                process=Process.sequential,
                full_output=True,
                share_crew=False,
            )
            # Kick off the crew's work and capture results
            results = crew.kickoff()
        
            # turn generate_interview_question into string and select substring after 'raw=' and before 'pydantic'

            st.write(generate_interview_questions.output.raw_output)
            st.write(interview_customer.output.raw_output)
            st.write(analyze_interview.output.raw_output)
            st.write(update_learnings.output.raw_output)
    
    else:
        st.write('Please click the button to start the interview')
