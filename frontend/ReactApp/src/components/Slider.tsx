import { useEffect, useRef } from "react";
import "./Slider.css"

interface SliderProps {
    value: number;
    min: number;
    max: number;
    onChange: (v: number) => void;
}

export function Slider({ value, min, max, onChange }: SliderProps) {
    const ref = useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (!ref.current) return;
        const percent = ((value - min) / (max - min)) * 100;
        ref.current.style.background = `linear-gradient(to right, var(--accent) 0%, var(--accent) ${percent}%, rgba(255,255,255,0.2) ${percent}%, rgba(255,255,255,0.2) 100%)`;
    }, [value, min, max]);

    return (
        <input
            ref={ref}
            type="range"
            min={min}
            max={max}
            value={value}
            onChange={(e) => onChange(Number(e.target.value))}
            className="slider"
        />
    );
}