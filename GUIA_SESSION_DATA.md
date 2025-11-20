# 📚 Guía: Dónde poner la Data de Perfiles (session_data)

## 🎯 Resumen

La data de perfiles se envía desde el **Frontend** al Backend cuando el usuario hace una consulta. El Backend la usa para filtrar qué documentos puede ver el usuario según sus roles.

---

## 📋 Estructura de la Data

La data debe seguir esta estructura (igual que `data_unemi.json`):

```json
{
  "0706191558": {
    "perfiles": [
      {
        "status": true,
        "es_estudiante": true,
        "es_profesor": false,
        "es_administrativo": false
      },
      {
        "status": true,
        "es_estudiante": false,
        "es_profesor": true,
        "es_administrativo": false
      }
    ]
  }
}
```

---

## 🚀 Opciones para Enviar la Data

### **OPCIÓN 1: Desde localStorage (Recomendado para Demo)**

**1. Guarda la data cuando el usuario hace login:**

```javascript
// En tu componente de login
import sessionDataJson from './data/data_unemi.json';

function handleLogin(cedula) {
  // Guardar en localStorage
  const userData = {
    [cedula]: sessionDataJson[cedula]
  };
  localStorage.setItem('user_session_data', JSON.stringify(userData));
}
```

**2. El Chatbot ya está configurado para leerlo automáticamente.**

---

### **OPCIÓN 2: Desde un Store de Svelte (Recomendado para Producción)**

**1. Crea un store:** `frontend/src/stores/userStore.js`

```javascript
import { writable } from 'svelte/store';

export const userStore = writable({
  sessionData: {},
  currentUser: null
});

// Función para actualizar
export function setUserSession(cedula, data) {
  userStore.update(store => ({
    ...store,
    sessionData: { [cedula]: data },
    currentUser: cedula
  }));
}
```

**2. Actualiza Chatbot.svelte:**

```javascript
import { userStore } from '../stores/userStore.js';

// En loadSessionData():
sessionData = $userStore.sessionData;
```

---

### **OPCIÓN 3: Desde una API Django (Más Seguro)**

**1. Crea endpoint en Django:** `chatbot/views.py`

```python
class UserSessionView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Obtener data del usuario autenticado
        user = request.user
        # ... lógica para obtener perfiles ...
        
        session_data = {
            user.cedula: {
                "perfiles": [
                    {
                        "status": True,
                        "es_estudiante": user.is_student,
                        "es_profesor": user.is_professor,
                        "es_administrativo": user.is_admin
                    }
                ]
            }
        }
        
        return Response(session_data)
```

**2. Actualiza Chatbot.svelte:**

```javascript
async function loadSessionData() {
  try {
    const response = await fetch('/api/user/session/', {
      headers: {
        'Authorization': `Bearer ${getAuthToken()}`
      }
    });
    sessionData = await response.json();
  } catch (e) {
    console.error('Error cargando session:', e);
  }
}
```

---

### **OPCIÓN 4: Para Testing/Demo - Cargar JSON Directamente**

**Actualiza Chatbot.svelte:**

```javascript
import sessionDataJson from '../../balcondemo/app/data/data_unemi.json';

function loadSessionData() {
  // Usar solo el usuario actual (ej: "0706191558")
  const currentUserCedula = "0706191558"; // O desde props/params
  sessionData = {
    [currentUserCedula]: sessionDataJson[currentUserCedula]
  };
}
```

---

## ✅ ¿Cómo Verificar que Funciona?

**1. Abre las DevTools del navegador (F12)**

**2. En la pestaña Network, busca la llamada a `/api/chatbot/chat/`**

**3. Verifica el Request Payload:**

```json
{
  "message": "¿Cómo justificar una falta?",
  "session_data": {
    "0706191558": {
      "perfiles": [...]
    }
  }
}
```

**4. Verifica la Response - debe incluir `debug_roles`:**

```json
{
  "type": "rag_response",
  "text": "...",
  "debug_roles": ["general", "estudiantes"],
  ...
}
```

---

## 🔍 Debugging

Si no funciona, revisa:

1. **¿Se está enviando session_data?**
   - Abre DevTools → Network → Revisa el Request Payload

2. **¿El backend detecta los roles?**
   - Revisa `debug_roles` en la respuesta
   - Revisa los logs del servidor Django

3. **¿Los perfiles tienen `status: true`?**
   - Solo los perfiles con `status: true` se consideran

4. **¿Las categorías están correctas?**
   - `es_estudiante: true` → agrega `"estudiantes"`
   - `es_profesor: true` → agrega `"docentes"`
   - `es_administrativo: true` → agrega `"administrativos"`

---

## 📁 Organización de Documentos

Recuerda que los documentos deben estar organizados así:

```
documentos_unemi/
  ├── general/          ← Todos ven esto
  ├── estudiantes/      ← Solo estudiantes
  ├── docentes/         ← Solo profesores
  └── administrativos/  ← Solo administrativos
```

Y ejecutar `python cargar_docs.py` después de organizarlos.

---

## 🎯 Ejemplo Completo de Uso

**1. En tu componente de login:**

```javascript
import sessionDataJson from './data/data_unemi.json';

function login(cedula) {
  // Autenticar...
  
  // Guardar session_data
  const userSession = {
    [cedula]: sessionDataJson[cedula]
  };
  localStorage.setItem('user_session_data', JSON.stringify(userSession));
  
  // Redirigir al chat
  navigate('/chatbot');
}
```

**2. El Chatbot automáticamente:**
   - Lee `localStorage.getItem('user_session_data')`
   - Lo envía en cada mensaje
   - El backend filtra documentos según roles

---

¡Listo! 🎉

