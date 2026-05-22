import "./LoadingSpinner.css";
import { useState, useEffect } from "react";

export default function LoadingSpinner() {
    const [dots, setDots] = useState(1);

    useEffect(() => {
        const interval = setInterval(() => {
            setDots(prev => (prev === 3 ? 1 : prev + 1));
        }, 500);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="loading-container">
            <div className="spinner"></div>
            <p>Laddar{".".repeat(dots)}</p>
        </div>
    );
}
