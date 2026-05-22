import './index.css'
import Button from "../components/Button";
import { useNavigate, type NavigateFunction } from "react-router-dom";
import { useEffect, useState } from "react";
//https://www.svgrepo.com/svg/451659/go-next
// import Start from "../assets/start.svg"
//https://www.svgrepo.com/svg/529212/skip-next -- Modified removed right line
import Start from "../assets/start.svg"
//https://www.svgrepo.com/svg/529644/history
import History from "../assets/history.svg"
//https://www.svgrepo.com/svg/528998/glasses
import Teacher from "../assets/teacher.svg"
import { canAccessControlPanel, getCurrentBackendUser } from "../services/entraAuth";

export default function index(){
    const navigate = useNavigate()
    const [showControlPanelButton, setShowControlPanelButton] = useState(false);

    useEffect(() => {
        let ignore = false;

        async function checkControlPanelAccess(){
            try {
                const user = await getCurrentBackendUser();
                if(!ignore){
                    setShowControlPanelButton(Boolean(user?.can_access_control_panel || canAccessControlPanel(user?.role)));
                }
            } catch {
                if(!ignore){
                    setShowControlPanelButton(false);
                }
            }
        }

        void checkControlPanelAccess();

        return () => {
            ignore = true;
        }
    }, []);

    function go_to_questionselect(navigate : NavigateFunction){
        navigate("/questionselect")
    }
    function go_to_history(navigate : NavigateFunction){
        navigate("/history")
    }
    function go_to_control(navigate : NavigateFunction){
        navigate("/controlpanel")
    }

    return(
        <>
            <div className='maindiv-index'>
                <h1>Välkommen till <b>Övning i läkemedelsberäkning</b>!</h1>
                <div className='index-box'>
                    <div className='index-text-box'>
                        <h2>Börja öva nu!</h2>
                        <p>Träna i din egen takt och få hjälp längs vägen. Välj en kurs och börja redan nu.</p>
                    </div>
                    <div className='index-button-box'>
                        <div className='index-button'>
                            <Button text='Börja Öva' onClick={() => {go_to_questionselect(navigate)}} img={[Start,"Start"]}></Button>
                        </div>
                        <div className='index-button'>
                            <Button text='Se Tidigare Övningar' onClick={() => {go_to_history(navigate)}} img={[History,"History"]}></Button>
                        </div>
                        {showControlPanelButton &&(
                            <div className='index-button'>
                                <Button text='Lärare Kontrollpanel' onClick={() => {go_to_control(navigate)}} img={[Teacher,"Teacher"]} color='var(--secondary-button)' hover='var(--secondary-button-hover)'></Button>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        
        </>
    )
}
