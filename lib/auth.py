"""
Autenticação simples com streamlit-authenticator.

Configuração via st.secrets (configurar em Streamlit Cloud → App settings → Secrets):

    [auth]
    cookie_name = "avaliador_nucleo"
    cookie_key = "<random string>"
    cookie_expiry_days = 30

    [auth.credentials.usernames.joao]
    email = "joao@nucleo.pt"
    name = "Joao Grilo"
    password = "<bcrypt hash>"

    [auth.credentials.usernames.equipa]
    email = "equipa@nucleo.pt"
    name = "Equipa Nucleo"
    password = "<bcrypt hash>"

Para gerar passwords bcrypt:
    python -c "import streamlit_authenticator as stauth; print(stauth.Hasher(['minhapassword']).generate()[0])"

Em desenvolvimento local sem secrets, a auth é desligada (login automático).
"""

import streamlit as st


def _config_disponivel() -> bool:
    try:
        return "auth" in st.secrets and "credentials" in st.secrets["auth"]
    except Exception:
        return False


def login_screen():
    """
    Mostra ecrã de login. Devolve (autenticado: bool, name: str, username: str).

    Em desenvolvimento (sem secrets), retorna (True, "Dev", "dev") sem login.
    """
    if not _config_disponivel():
        # Modo desenvolvimento: skip auth
        st.session_state["authenticated"] = True
        st.session_state["name"] = "Dev (sem auth)"
        st.session_state["username"] = "dev"
        return True, "Dev (sem auth)", "dev"

    # streamlit-authenticator
    try:
        import streamlit_authenticator as stauth
    except ImportError:
        st.error(
            "streamlit-authenticator não instalado. "
            "Adiciona ao requirements.txt e re-deploy."
        )
        return False, "", ""

    cfg = st.secrets["auth"]

    # Build credentials dict no formato esperado
    credentials = {"usernames": {}}
    for username, info in cfg["credentials"]["usernames"].items():
        credentials["usernames"][username] = {
            "email": info.get("email", ""),
            "name": info.get("name", username),
            "password": info["password"],
        }

    authenticator = stauth.Authenticate(
        credentials,
        cookie_name=cfg.get("cookie_name", "avaliador_cookie"),
        cookie_key=cfg.get("cookie_key", "default-key-CHANGE-ME"),
        cookie_expiry_days=cfg.get("cookie_expiry_days", 30),
    )

    name, auth_status, username = authenticator.login(location="main")

    if auth_status is False:
        st.error("Username ou password errados")
        return False, "", ""
    if auth_status is None:
        st.warning("Faz login para continuar")
        return False, "", ""

    # Auth ok
    st.session_state["authenticated"] = True
    st.session_state["name"] = name
    st.session_state["username"] = username

    # Logout button na sidebar
    with st.sidebar:
        st.write(f"Olá, **{name}**")
        authenticator.logout("Logout", location="sidebar")

    return True, name, username
