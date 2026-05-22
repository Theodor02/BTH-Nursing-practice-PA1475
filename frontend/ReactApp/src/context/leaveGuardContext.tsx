import { createContext, useContext, useState } from "react";

type GuardContextType = {
    shouldBlock: boolean;
    setShouldBlock: (v: boolean) => void;
    onLeave?: () => void;
    setOnLeave: (fn: (() => void) | undefined) => void;
};

const LeaveGuardContext = createContext<GuardContextType | null>(null);

export function LeaveGuardProvider({ children }: { children: React.ReactNode }) {
    const [shouldBlock, setShouldBlock] = useState(false);
    const [onLeave, setOnLeave] = useState<(() => void) | undefined>();

    return (
        <LeaveGuardContext.Provider value={{ shouldBlock, setShouldBlock, onLeave, setOnLeave }}>
            {children}
        </LeaveGuardContext.Provider>
    );
}

export function useLeaveGuard() {
    const ctx = useContext(LeaveGuardContext);
    if (!ctx) throw new Error("useLeaveGuard must be used within provider");
    return ctx;
}