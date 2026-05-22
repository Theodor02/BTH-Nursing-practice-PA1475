import './Button.css'
import { useRef } from 'react';

interface props{
    text: string;
    onClick: () => void;
    disabled?: boolean;
    color?: string;
    hover?: string;
    img?: string[] | null;
    
}

export default function button({text, onClick, disabled = false, color, img, hover}: props){

    const btnRef = useRef<HTMLButtonElement>(null);

    const handleClick = () => {
        onClick();
        btnRef.current?.blur(); // remove focus after click
    };

    return(
        <button onClick={handleClick} className='button-component' disabled={disabled} style={{'--btn-bg': color,'--btn-hover': hover} as React.CSSProperties}>
            
            {img != null && <img src={img[0]} alt={img[1]}/>}
            
            {text}
            
        </button>
    )
}





