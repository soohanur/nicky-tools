import AuthAside from "@/components/forms/AuthAside";
import LoginForm from "@/components/forms/LoginForm";
import { auth } from "@/data/site";

export const metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <div className="auth">
      <AuthAside {...auth.login} />
      <div className="auth-main">
        <LoginForm />
      </div>
    </div>
  );
}
