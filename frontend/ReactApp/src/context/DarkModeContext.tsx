// Inspiration from https://medium.com/lets-make-something-up/creating-light-dark-mode-on-a-react-app-with-context-589a5465f639

import React, { createContext, useState, useEffect} from "react";

type DarkModeContextType = {
    darkMode: boolean;
    toggleDarkMode: () => void;
};

const DarkModeContext = createContext<DarkModeContextType | undefined>(undefined)

type DarkModeProviderProps = {
    children: React.ReactNode;
};

function DarkModeProvider({children}:DarkModeProviderProps){
    const [darkMode, setDarkMode] = useState(false);

    const toggleDarkMode = () => {
        setDarkMode(!darkMode);
    };
    
    useEffect(() => {
        if (darkMode) {
            document.body.classList.add("dark");
        } else {
            document.body.classList.remove("dark");
        }
    }, [darkMode]);

    return(
        <div>
            <DarkModeContext.Provider value={{darkMode, toggleDarkMode}}>
                {children}
            </DarkModeContext.Provider>
        </div>
    )
};


export {DarkModeContext, DarkModeProvider};