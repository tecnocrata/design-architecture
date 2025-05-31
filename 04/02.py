from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
import os

# Establecer la API key desde variable de entorno
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_KEY")

# 1. Crear memoria para la conversación
memory = ConversationBufferMemory(return_messages=True)

# 2. Crear el prompt con historial de mensajes
prompt = ChatPromptTemplate.from_messages([
    ("system", "Eres un asistente conversacional amigable y útil."),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}")
])

# 3. Crear el modelo LLM
llm = ChatOpenAI(temperature=0.7, model="gpt-3.5-turbo")

# 4. Crear la cadena conversacional
conversation = ConversationChain(
    memory=memory,
    prompt=prompt,
    llm=llm,
    verbose=True
)

# 5. Ejecutar una conversación de ejemplo
conversation.invoke({"input": "Hola, ¿puedes recordarme mi nombre si te lo digo?"})
conversation.invoke({"input": "Me llamo Enrique, recuérdalo."})
response = conversation.invoke({"input": "¿Cuál es mi nombre?"})

print("🧠 Respuesta final:", response['response'])