import { DarkModeContext } from "../context/DarkModeContext";
import { useLeaveGuard } from "../context/leaveGuardContext";
import { useContext, useEffect, useRef, useState } from "react";
import "./Header.css";
import { useLocation, useNavigate } from "react-router-dom";
import Button from "./Button";
import Tab from "./tab";
import { useScreenWidth } from "../services/screenwidth";
import {
    clearMicrosoftSession,
    deactivateCurrentAccount,
    getCurrentBackendUser,
    logoutBackendSession,
    logoutMicrosoftSession,
    type BackendUser,
} from "../services/entraAuth";

/* ATTRIBUTION & LICENSING:
  - Exit Icon: https://www.svgrepo.com/svg/528912/close-circle (CC Attribution)
  - Account Icon: https://www.svgrepo.com/svg/529279/user-circle (CC Attribution)
  - Delete Account Icon: https://www.svgrepo.com/svg/528907/clipboard-remove (CC Attribution)
  - Logout Icon: https://www.svgrepo.com/svg/529057/logout-2 (CC Attribution)
  - Sun Icon: https://www.svgrepo.com/svg/529971/sun-2 (CC Attribution)
  - Moon Icon: https://www.svgrepo.com/svg/529729/moon (CC Attribution)
  - Home Icons: https://www.svgrepo.com/svg/529027/home-1 (CC Attribution)
  - Arrow Icon: https://www.svgrepo.com/svg/529550/double-alt-arrow-up (CC Attribution)
------------------------------------------------------------------*/
import exit from "../assets/exit.svg";
import User from "../assets/account-icon.svg";
import deleteaccount from "../assets/deleteaccount.svg";
import logout from "../assets/logout.svg";
import down from "../assets/down.svg";
import Sun from "../assets/sun.svg";
import Moon from "../assets/moon.svg";
import Homelight from "../assets/home-light.svg";
import Homedark from "../assets/home-dark.svg";

export default function Header(){
    const location = useLocation();
    const ctx = useContext(DarkModeContext);
    const navigate = useNavigate();
    const accountMenuRef = useRef<HTMLDivElement | null>(null);
    const [isLoggingOut, setIsLoggingOut] = useState(false);
    const [isDeletingAccount, setIsDeletingAccount] = useState(false);
    const [showDeleteAccountConfirm, setShowDeleteAccountConfirm] = useState(false);
    const [deleteAccountError, setDeleteAccountError] = useState<string | null>(null);
    const [currentUser, setCurrentUser] = useState<BackendUser | null>(null);
    const [isLoadingCurrentUser, setIsLoadingCurrentUser] = useState(true);
    const [accountMenuOpen, setAccountMenuOpen] = useState(false);
    const [tab, setTab] = useState(0);
    const deleteAccountDescription =
        "Det h\u00e4r avaktiverar ditt konto i Fokus Lokus och tar bort dina sparade sessioner. \u00c4r du s\u00e4ker p\u00e5 att du vill forts\u00e4tta?";
    const width = useScreenWidth();
    const [pendingPath, setPendingPath] = useState<string | null>(null);
    const [showLeaveConfirm, setShowLeaveConfirm] = useState(false);
    useEffect(() => {
        if(location.pathname == "/questions" || location.pathname == "/questionselect"){
            setTab(1);
        }
        if(location.pathname == "/history" || location.pathname.startsWith("/attemptinfo")){
            setTab(2);
        }
        if(location.pathname == "/" || location.pathname == "/home" ||location.pathname == "/controlpanel"){
            setTab(0);
        }
    },[location]);

    const { shouldBlock, onLeave } = useLeaveGuard();

    function guardedNavigate(path: string) {
        if (shouldBlock) {
            setPendingPath(path);
            setShowLeaveConfirm(true);
            return;
        }

        navigate(path);
    }

    const confirmLeave = (save: boolean) => {
        if (pendingPath) {
            save && onLeave?.();
            navigate(pendingPath);
        }
        setPendingPath(null);
        setShowLeaveConfirm(false);
    };

    const cancelLeave = () => {
        setPendingPath(null);
        setShowLeaveConfirm(false);
    };

    useEffect(() => {
        let ignore = false;

        const loadCurrentUser = async () => {
            setIsLoadingCurrentUser(true);

            try {
                const user = await getCurrentBackendUser();
                if (!ignore) {
                    setCurrentUser(user);
                }
            } catch (error) {
                console.error("Could not load current backend user:", error);
                if (!ignore) {
                    setCurrentUser(null);
                }
            } finally {
                if (!ignore) {
                    setIsLoadingCurrentUser(false);
                }
            }
        };

        void loadCurrentUser();

        return () => {
            ignore = true;
        };
    }, []);

    useEffect(() => {
        const handler = (e: BeforeUnloadEvent) => {
            if (shouldBlock) {
                e.preventDefault();
                e.returnValue = "";
            }
        };

        window.addEventListener("beforeunload", handler);
        return () => window.removeEventListener("beforeunload", handler);
    }, [shouldBlock]);

    useEffect(() => {
        setAccountMenuOpen(false);
    }, [location.pathname]);

    useEffect(() => {
        if (!accountMenuOpen) {
            return;
        }

        const handlePointerDown = (event: MouseEvent) => {
            if (
                accountMenuRef.current &&
                !accountMenuRef.current.contains(event.target as Node)
            ) {
                setAccountMenuOpen(false);
            }
        };

        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === "Escape") {
                setAccountMenuOpen(false);
            }
        };

        document.addEventListener("mousedown", handlePointerDown);
        document.addEventListener("keydown", handleKeyDown);

        return () => {
            document.removeEventListener("mousedown", handlePointerDown);
            document.removeEventListener("keydown", handleKeyDown);
        };
    }, [accountMenuOpen]);

    if (!ctx) return null;
    const { darkMode, toggleDarkMode } = ctx;
    const accountEmail = isLoadingCurrentUser
        ? "H\u00e4mtar konto..."
        : (currentUser?.email ?? "Ok\u00e4nd anv\u00e4ndare");
    const accountRole = isLoadingCurrentUser
        ? "H\u00e4mtar roll..."
        : (currentUser?.role ?? "Ingen roll");
    const canDeleteOwnAccount =
        !isLoadingCurrentUser &&
        currentUser !== null &&
        currentUser.role !== "SuperAdmin";

    const resetToLoginPage = () => {
        window.location.replace(
            `${window.location.origin}${window.location.pathname}${window.location.search}#/`
        );
    };

    const handleLogout = async () => {
        if (isLoggingOut || isDeletingAccount) {
            return;
        }

        setAccountMenuOpen(false);
        setIsLoggingOut(true);

        try {
            await logoutBackendSession();
        } catch (error) {
            console.error("Backend logout failed:", error);
        }

        try {
            await logoutMicrosoftSession();
            return;
        } catch (error) {
            console.error("Microsoft logout failed:", error);
            try {
                await clearMicrosoftSession();
            } catch (clearError) {
                console.error("Local Microsoft logout failed:", clearError);
            } finally {
                resetToLoginPage();
                setIsLoggingOut(false);
            }
        }
    };

    const handleDeleteAccount = async () => {
        if (isDeletingAccount || isLoggingOut) {
            return;
        }

        setIsDeletingAccount(true);
        setDeleteAccountError(null);

        try {
            await deactivateCurrentAccount();

            try {
                await logoutMicrosoftSession();
                return;
            } catch (logoutError) {
                console.error("Microsoft logout after account deactivation failed:", logoutError);
                try {
                    await clearMicrosoftSession();
                } catch (clearError) {
                    console.error("Local Microsoft cleanup after account deactivation failed:", clearError);
                }
            }

            resetToLoginPage();
        } catch (error) {
            console.error("Account deactivation failed:", error);
            setDeleteAccountError(
                error instanceof Error && error.message.trim()
                    ? error.message
                    : "Kunde inte avaktivera kontot just nu.",
            );
        } finally {
            setIsDeletingAccount(false);
        }
    };

    return(
        <>
            {showLeaveConfirm && (
                <div className="overlay" onClick={cancelLeave}>
                    <div
                        className="delete-account-modal"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="delete-account-header">
                            <h2>Obesparade frågor!</h2>
                            <button className="table-button" onClick={cancelLeave} aria-label="Avbryt">
                                <img src={exit} alt="Stäng" />
                            </button>
                        </div>
                        <p>Du har ej sparat dina svar. Vill du verkligen lämna sidan?</p>

                        <div className="actions">
                            <Button text="Lämna" onClick={() => confirmLeave(false)} color="red" hover="red"></Button>
                            <Button text="Lämna och Spara" onClick={() => confirmLeave(true)}></Button>
                        </div>
                    </div>
                </div>
            )}
            <header>
                <div className="Header-div">
                    <div className="header-left">
                        <button className="home-button" onClick={() => guardedNavigate("/home")} aria-label="Go to Home">
                            {darkMode ? <img src={Homedark} alt="Homedark" /> : <img src={Homelight} alt="Homelight" />}
                        </button>
                        <div className="tabs">
                            <Tab text="Öva" selected={tab == 1} on_Click={()=> guardedNavigate("/questionselect")} />
                            <Tab text="Historik" selected={tab == 2} on_Click={()=> guardedNavigate("/history")} />
                        </div>
                    </div>
                    <div className="header-right">
                        <button className="darkmode-button" onClick={toggleDarkMode} aria-label="Toggle dark mode">
                            {darkMode ? <img src={Sun} alt="Sun" />: <img src={Moon} alt="Moon" />}
                        </button>
                        <div className="account-menu-shell" ref={accountMenuRef}>
                            {width < 400 ? <button className="account-button" onClick={() => setAccountMenuOpen((open) => !open)} aria-label="Visa kontomeny" aria-expanded={accountMenuOpen} disabled={isLoggingOut || isDeletingAccount} title="Konto">
                                <img src={User} alt="User" />
                            </button>
                            :
                            <button
                                className="account-menu-button"
                                aria-label="Visa kontomeny"
                                aria-expanded={accountMenuOpen}
                                onClick={() => setAccountMenuOpen((open) => !open)}
                                disabled={isLoggingOut || isDeletingAccount}
                                title="Konto"
                            >
                                <img src={User} alt="Användare" />
                                <span>Konto</span>
                                <img src={down} alt="ner" />
                            </button>
                            }

                            {accountMenuOpen ? (
                                <div className="account-menu-panel" role="menu">
                                    <div className="account-menu-summary">
                                        <div className="account-menu-avatar" aria-hidden="true">
                                            <img src={User} alt="Användare" />
                                        </div>
                                        <div className="account-menu-meta">
                                            <span className="account-menu-label">{accountRole}</span>
                                            <span className="account-menu-email">{accountEmail}</span>
                                        </div>
                                    </div>

                                    <div className="account-menu-actions">
                                        {canDeleteOwnAccount ? (
                                            <div className="button-wrapper">
                                                <Button
                                                    text="Avaktivera kontot"
                                                    onClick={() => {
                                                        setAccountMenuOpen(false);
                                                        setDeleteAccountError(null);
                                                        setShowDeleteAccountConfirm(true);
                                                    }}
                                                    disabled={isLoggingOut || isDeletingAccount}
                                                    color="#db6767"
                                                    hover="#db6767"
                                                    img={[deleteaccount, "Avaktivera konto"]}
                                                ></Button>
                                            </div>
                                        ) : null}
                                        <div className="button-wrapper">
                                            <Button
                                                text={isLoggingOut ? "Loggar ut..." : "Logga ut"}
                                                onClick={() => void handleLogout()}
                                                disabled={isLoggingOut || isDeletingAccount}
                                                img={[logout, "Logga ut"]}
                                            ></Button>
                                        </div>
                                    </div>
                                </div>
                            ) : null}
                        </div>
                    </div>
                </div>
            </header>

            {showDeleteAccountConfirm ? (
                <div
                    className="overlay"
                    onClick={() => {
                        if (!isDeletingAccount) {
                            setShowDeleteAccountConfirm(false);
                        }
                    }}
                >
                    <div
                        className="delete-account-modal"
                        onClick={(event) => event.stopPropagation()}
                    >
                        <div className="delete-account-header">
                            <h2>Avaktivera konto?</h2>
                            <button className="table-button" onClick={() => setShowDeleteAccountConfirm(false)} disabled={isDeletingAccount} aria-label="Stäng avaktivera konto dialog">
                                <img src={exit} alt="Stäng" />
                            </button>
                        </div>
                        <p>{deleteAccountDescription}</p>
                        {deleteAccountError ? (
                            <p className="delete-account-error">{deleteAccountError}</p>
                        ) : null}
                        <div className="delete-account-actions">
                            <div className="button-wrapper">
                                <Button
                                    img={[deleteaccount, "Avaktivera konto"]}
                                    onClick={() => void handleDeleteAccount()}
                                    disabled={isDeletingAccount}
                                    text={isDeletingAccount ? "Avaktiverar..." : "Avaktivera konto"}
                                    color="#db6767"
                                    hover="#db6767"
                                ></Button>
                            </div>
                        </div>
                    </div>
                </div>
            ) : null}
        </>
    )
}
