import AuthAside from "@/components/forms/AuthAside";
import RegisterForm from "@/components/forms/RegisterForm";
import { auth } from "@/data/site";

export const metadata = { title: "Create account" };

export default function RegisterPage() {
  return (
    <div className="auth">
      <AuthAside {...auth.register} />
      <div className="auth-main">
        <RegisterForm />
      </div>
    </div>
  );
}
