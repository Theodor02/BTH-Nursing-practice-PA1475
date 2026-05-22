import "./tab.css"

interface props{
    selected: boolean;
    text: string;
    expand?: string;
    on_Click: () => void;
}

export default function Tab({selected, text, expand, on_Click}:props){
    return(
        <div className={`tab ${selected && "selected"} ${expand == "horizontal" && "exp-horizontal"}`} onClick={on_Click} tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter") on_Click(); }} role="button" aria-pressed={selected}>
            <span>{text}</span>
            <hr className={selected ? "hr-animate" : ""} />
        </div>
    )
}