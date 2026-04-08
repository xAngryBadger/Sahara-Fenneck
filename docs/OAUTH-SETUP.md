# OAuth - Configuração UMA VEZ (só você, o desenvolvedor)

**Os usuários nunca veem isso.** Eles só clicam "Entrar com Google" ou "Entrar com Microsoft" e fazem login com email/senha.

**Você** configura UMA VEZ em `src/integrations/oauth_defaults.py`:

```python
EMBEDDED_GOOGLE_CLIENT_ID = "seu_id.apps.googleusercontent.com"
EMBEDDED_MICROSOFT_CLIENT_ID = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

Depois disso, gera o instalador e distribui. Pronto.

---

## Como criar as credenciais (5 min cada)

### Google

1. <https://console.cloud.google.com/apis/credentials>
2. Criar credenciais > ID do cliente OAuth
3. Tipo: **Aplicativo para computador**
4. Nome: Sahara Fennec
5. Copiar o ID do cliente → colar em `EMBEDDED_GOOGLE_CLIENT_ID`
6. Tela de consentimento: configurar nome e e-mail (modo teste = até 100 usuários)

### Microsoft

1. <https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade>
2. Novo registro > Nome: Sahara Fennec
3. URI de redirecionamento: **Cliente público/nativo** > `http://localhost`
4. Copiar ID do aplicativo → colar em `EMBEDDED_MICROSOFT_CLIENT_ID`
5. Permissões de API: Mail.Send, Calendars.Read, Files.ReadWrite, Sites.ReadWrite.All, User.Read, offline_access
