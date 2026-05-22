import "./Modal.css";

interface props{
    purpose:string;
    isOpen:boolean;
    onClose:()=>void;
    children:React.ReactNode;
}

export default function Modal({purpose, isOpen, onClose, children}:props){
    if(!isOpen) return null;

    return( 
        <div className="overlay">
            <div className="modal">
                <span id="modalpurpose">{purpose}</span>
                <button onClick={onClose} id="modal_exit">X</button>
                <hr id="modalline" />
                {children}
            </div>
        </div>
    )

}