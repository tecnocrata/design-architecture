from langchain_openai import ChatOpenAI  # Updated import
from langchain.prompts import PromptTemplate
# from langchain.chains import LLMChain
import os

# Asegúrate de tener tu clave en la variable de entorno OPENAI_KEY
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_KEY")

# 1. Definimos una plantilla de prompt
prompt = PromptTemplate(
    input_variables=["question"],
    template="Eres un asistente útil. Responde con claridad: {question}"
)

# 2. Inicializamos el modelo de OpenAI (puedes usar 'gpt-3.5-turbo' o 'gpt-4')
llm = ChatOpenAI(temperature=0.7, model="gpt-3.5-turbo")

# 3. Creamos una LLMChain que combina prompt + modelo
# chain = LLMChain(prompt=prompt, llm=llm)
chain = prompt | llm

# 4. Ejecutamos una consulta
question = "¿Qué es el la inteligencia artificial? Dame dos definiciones una practica (desde el punto de vista tecnico) y otra filosófica"
response = chain.invoke(question)

print("🧠 Pregunta:", question)
print("📨 Respuesta del modelo:\n", response)
print("Solo respuesta:", response.content)