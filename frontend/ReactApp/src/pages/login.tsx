import { useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
//https://www.svgrepo.com/svg/523320/cloud-upload
import ssoIcon from "../assets/sso-icon.svg";
//https://www.svgrepo.com/svg/523308/cloud-plus
import ssoIconRegister from "../assets/sso-icon-register.svg";
import Button from "../components/Button";
//https://www.svgrepo.com/svg/528912/close-circle
import exit from "../assets/exit.svg";
import { DarkModeContext } from "../context/DarkModeContext";
import {
    clearMicrosoftSession,
    getSignedInAccount,
    handleMicrosoftRedirectResult,
    logoutMicrosoftSession,
    registerSignedInUser,
    registerWithMicrosoft,
    signInWithMicrosoft,
} from "../services/entraAuth";
import "./login.css";

type AuthenticationAction = "login" | "register";

export default function Login() {
    const navigate = useNavigate();
    const ctx = useContext(DarkModeContext);
    const [authenticatingAction, setAuthenticatingAction] = useState<AuthenticationAction | null>(null);
    const [loginError, setLoginError] = useState<string | null>(null);
    const [showRegistrationNotice, setShowRegistrationNotice] = useState(false);
    const [showWrongAccountNotice, setShowWrongAccountNotice] = useState(false);
    const [isLoggingOutMicrosoft, setIsLoggingOutMicrosoft] = useState(false);
    const genericAuthErrorMessage = "N\u00e5got gick fel vid autentiseringen.";
    const disallowedAccountMessage = "This account is not allowed to use the application.";
    const wrongAccountNoticeText =
        "Du verkar vara inloggad med ett Microsoft-konto som inte f\u00e5r anv\u00e4nda appen. Logga ut fr\u00e5n det kontot och f\u00f6rs\u00f6k sedan registrera ditt BTH-konto igen.";
    const isAuthenticating = authenticatingAction !== null;

    const isDisallowedAccountError = (error: unknown) => (
        error instanceof Error && error.message.includes(disallowedAccountMessage)
    );

    const getErrorMessage = (error: unknown) => {
        if (isDisallowedAccountError(error)) {
            return "Det valda Microsoft-kontot \u00e4r inte till\u00e5tet. Logga ut fr\u00e5n Microsoft och f\u00f6rs\u00f6k igen med ditt BTH-konto.";
        }

        if (error instanceof TypeError && error.message.includes("Failed to fetch")) {
            return "Kunde inte n\u00e5 backendens /login-endpoint. Kontrollera att backend/proxy \u00e4r ig\u00e5ng och att du k\u00f6r appen via samma origin som projektet \u00e4r konfigurerat f\u00f6r.";
        }

        if (error instanceof Error && error.message.trim().length > 0) {
            return `${genericAuthErrorMessage} ${error.message}`;
        }

        return `${genericAuthErrorMessage} Ladda om sidan och f\u00f6rs\u00f6k igen.`;
    };

    useEffect(() => {
        let isMounted = true;

        const checkSession = async () => {
            let handledMicrosoftRedirect = false;

            try {
                const redirectResult = await handleMicrosoftRedirectResult();
                if (!isMounted) {
                    return;
                }

                if (redirectResult) {
                    handledMicrosoftRedirect = true;
                    setAuthenticatingAction(redirectResult.action);
                    await registerSignedInUser(
                        redirectResult.result.account,
                        redirectResult.result.accessToken,
                    );

                    if (isMounted) {
                        navigate("/home");
                    }

                    return;
                }

                const account = await getSignedInAccount();
                if (!isMounted || !account) {
                    return;
                }

                await registerSignedInUser(account);

                if (isMounted) {
                    navigate("/home");
                }
            } catch (error) {
                console.error("Microsoft session restore failed:", error);
                if (isMounted) {
                    if (isDisallowedAccountError(error)) {
                        if (handledMicrosoftRedirect) {
                            setShowWrongAccountNotice(true);
                            setLoginError(getErrorMessage(error));
                            return;
                        }

                        try {
                            await clearMicrosoftSession();
                        } catch (clearError) {
                            console.error("Local Microsoft cleanup after passive restore failed:", clearError);
                        }
                        setLoginError(null);
                        return;
                    }
                    setLoginError(getErrorMessage(error));
                }
            } finally {
                if (isMounted) {
                    setAuthenticatingAction(null);
                }
            }
        };

        void checkSession();

        return () => {
            isMounted = false;
        };
    }, [navigate]);

    if (!ctx) {
        return null;
    }

    const { darkMode } = ctx;

    const handleAuthentication = async (action: AuthenticationAction) => {
        if (authenticatingAction) {
            return;
        }

        setLoginError(null);
        setShowWrongAccountNotice(false);
        setAuthenticatingAction(action);

        try {
            if (action === "register") {
                await registerWithMicrosoft();
            } else {
                await signInWithMicrosoft();
            }
        } catch (error) {
            console.error(`Microsoft ${action} failed:`, error);
            if (isDisallowedAccountError(error)) {
                setShowWrongAccountNotice(true);
            }
            setLoginError(getErrorMessage(error));
        } finally {
            setAuthenticatingAction(null);
        }
    };

    const handleRegisterClick = () => {
        if (isAuthenticating) {
            return;
        }

        setShowRegistrationNotice(true);
    };

    const confirmRegistration = () => {
        setShowRegistrationNotice(false);
        void handleAuthentication("register");
    };

    const handleMicrosoftLogout = async () => {
        if (isLoggingOutMicrosoft) {
            return;
        }

        setIsLoggingOutMicrosoft(true);
        setLoginError(null);

        try {
            await logoutMicrosoftSession();
        } catch (error) {
            console.error("Microsoft logout after wrong account failed:", error);
            try {
                await clearMicrosoftSession();
            } catch (clearError) {
                console.error("Local Microsoft cleanup after wrong account failed:", clearError);
            }

            setShowWrongAccountNotice(false);
            setLoginError(
                "Microsoft-utloggningen misslyckades. Jag rensade appens lokala session, testa registrera igen.",
            );
            setIsLoggingOutMicrosoft(false);
        }
    };

    return (
        <main>
            <div className="maindiv-login">
                <div className="text-box">
                    <h1>Övning i läkemedelsberäkning</h1>
                </div>
                <div className="login-box">
                    <div className="FL-box">
                        <h2>Välkommen!</h2>
                        <p>Logga in med ditt BTH-konto</p>
                    </div>

                    <div className="login-button-housing">
                        <div className="login-actions">
                            <div className="login-action">
                                <Button
                                    text={authenticatingAction === "login" ? "Loggar in..." : "Logga in"}
                                    onClick={() => void handleAuthentication("login")}
                                    disabled={isAuthenticating}
                                    img={[ssoIcon, "SSO signin"]}
                                />
                            </div>
                            <div className="login-action">
                                <Button
                                    text={authenticatingAction === "register" ? "Registrerar BTH Konto..." : "Registrera BTH Konto"}
                                    onClick={handleRegisterClick}
                                    disabled={isAuthenticating}
                                    color="var(--secondary-button)"
                                    hover="var(--secondary-button-hover)"
                                    img={[ssoIconRegister, "SSO signup"]}
                                />
                            </div>
                        </div>
                        {loginError ? <p className="login-error">{loginError}</p> : null}
                    </div>
                </div>
            </div>

            {showRegistrationNotice ? (
                <div
                    className="overlay"
                    onClick={() => setShowRegistrationNotice(false)}
                >
                    <div
                        className="login-notice-modal"
                        onClick={(event) => event.stopPropagation()}
                    >
                        <div className="delete-account-header">
                            <h2>Viktig information</h2>
                            <button className="table-button" onClick={() => setShowRegistrationNotice(false)} aria-label="Stäng registreringsinformation dialog">
                                <img src={exit} alt="Stäng" />
                            </button>
                        </div>
                        <p>
                            {`När du registrerar ditt BTH-konto första gången behöver du välja lösenord som inloggningssätt. Om du blir ombedd att använda Authenticator, klicka på "Logga in på annat sätt" och välj `}<b>"Logga in med lösenord".</b>
                        </p>
                        <div className="login-notice-actions">
                            <div className="button-wrapper">
                                <Button
                                    color="var(--secondary-button)"
                                    hover="var(--secondary-button-hover)"
                                    onClick={confirmRegistration}
                                    text="Fortsätt"
                                >
                                </Button>
                            </div>
                        </div>
                    </div>
                </div>
            ) : null}

            {showWrongAccountNotice ? (
                <div
                    className="overlay"
                    onClick={() => {
                        if (!isLoggingOutMicrosoft) {
                            setShowWrongAccountNotice(false);
                        }
                    }}
                >
                    <div
                        className="login-notice-modal"
                        onClick={(event) => event.stopPropagation()}
                    >
                        <div className="delete-account-header">
                            <h2>Fel Microsoft-konto</h2>
                            <button className="table-button" onClick={() => setShowWrongAccountNotice(false)} disabled={isLoggingOutMicrosoft} aria-label="Stäng registreringsinformation dialog">
                                <img src={exit} alt="Stäng" />
                            </button>
                        </div>
                        <p>{wrongAccountNoticeText}</p>
                        <div className="login-notice-actions">
                            <div className="button-wrapper">
                                <Button
                                    onClick={() => void handleMicrosoftLogout()}
                                    disabled={isLoggingOutMicrosoft}
                                    text={isLoggingOutMicrosoft ? "Loggar ut..." : "Logga ut fr\u00e5n Microsoft"}
                                >     
                                </Button>
                            </div>
                        </div>
                    </div>
                </div>
            ) : null}
        </main>
    );
}
