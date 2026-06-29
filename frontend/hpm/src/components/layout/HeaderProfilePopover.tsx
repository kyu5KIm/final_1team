import keyIcon from "../../assets/key.svg";
import logoutIcon from "../../assets/logout.svg";
import jiraIcon from "../../assets/jira.png";

interface HeaderProfilePopoverProps {
  email?: string;
  name?: string;
  empNo?: string;
  deptName?: string;
  rankName?: string;
  work?: string;
  loading?: boolean;
  jiraConnected?: boolean;
  jiraStatusLoading?: boolean;
  showProfileInfo?: boolean;
  showJiraConnect?: boolean;
  onJiraConnect?: () => void;
  onJiraReconnect?: () => void;
  onChangePassword?: () => void;
  onLogout?: () => void;
}

const displayValue = (value?: string, loading?: boolean) => {
  if (loading) return "...";
  return value || "-";
};

export default function HeaderProfilePopover({
  email,
  name,
  empNo,
  deptName,
  rankName,
  work,
  loading,
  jiraConnected,
  jiraStatusLoading,
  showProfileInfo = true,
  showJiraConnect = true,
  onJiraConnect,
  onChangePassword,
  onLogout,
  onJiraReconnect,
}: HeaderProfilePopoverProps) {
  const jiraDisabled = jiraStatusLoading;

  return (
    <section
      aria-label="사용자 프로필"
      className="absolute right-0 top-[50px] z-50 w-[384px] overflow-hidden rounded-[12px] border border-[#E6E1E6] bg-[#FFFDFD] shadow-[1px_1px_14px_4px_rgba(230,228,228,0.25)]"
      data-name="user-profile"
    >
      {showProfileInfo ? (
        <>
          <div className="px-[26px] pb-[24px] pt-[26px]">
            <div className="h-[96px] rounded-[10px] bg-[#F6F5FA] px-[18px] py-[20px]">
              <p className="m-0 text-[17px] font-medium leading-[1.2] text-[#141414]">
                {loading ? "..." : name ? `${name}님` : "-"}
              </p>
              <a
                className="mt-[14px] block text-[15px] font-normal leading-[1.2] text-[#623FB5] underline"
                href={email ? `mailto:${email}` : undefined}
              >
                {displayValue(email, loading)}
              </a>
            </div>

            <dl className="mt-[26px] grid grid-cols-[1fr_auto] gap-y-[20px] text-[15px] font-normal leading-[1.2]">
              <dt className="text-[#969696]">사번</dt>
              <dd className="m-0 text-right text-[#141414]">{displayValue(empNo, loading)}</dd>
              <dt className="text-[#969696]">부서</dt>
              <dd className="m-0 text-right text-[#141414]">{displayValue(deptName, loading)}</dd>
              <dt className="text-[#969696]">직급</dt>
              <dd className="m-0 text-right text-[#141414]">{displayValue(rankName, loading)}</dd>
              <dt className="text-[#969696]">직무</dt>
              <dd className="m-0 text-right text-[#141414]">{displayValue(work, loading)}</dd>
            </dl>
          </div>

          <div className="h-px w-full bg-[#E6E1E6]" />
        </>
      ) : null}
      <div className="flex flex-col gap-[15px] px-[26px] py-[22px]">
          {showJiraConnect ? (
            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={jiraDisabled ? undefined : onJiraConnect}
                disabled={jiraDisabled}
                className={`flex items-center gap-[10px] rounded-[5px] border-0 bg-transparent p-0 text-[15px] font-normal leading-[1.2] transition-all duration-150 ease-out ${
                  jiraDisabled
                    ? "cursor-default text-[#969696]"
                    : "text-[#141414] hover:text-[#623FB5] active:scale-[0.98]"
                }`}
              >
                <img src={jiraIcon} alt="" className="size-[20px] shrink-0 object-contain" />
                <span>
                  {jiraStatusLoading
                    ? "Jira 연동 확인 중"
                    : jiraConnected
                      ? "Jira 연동됨"
                      : "Jira 연동하기"}
                </span>
              </button>
              {jiraConnected && !jiraStatusLoading ? (
                <button
                  type="button"
                  onClick={onJiraReconnect}
                  className="text-[13px] text-[#969696] hover:text-[#623FB5] transition-colors underline"
                >
                  재연동
                </button>
              ) : null}
            </div>
          ) : null}
        <button
          type="button"
          onClick={onChangePassword}
          className="flex items-center gap-[10px] rounded-[5px] border-0 bg-transparent p-0 text-[15px] font-normal leading-[1.2] text-[#141414] transition-all duration-150 ease-out hover:text-[#623FB5] active:scale-[0.98]"
        >
          <img src={keyIcon} alt="" className="size-[20px] shrink-0" />
          <span>비밀번호 변경</span>
        </button>
        <button
          type="button"
          onClick={onLogout}
          className="flex items-center gap-[10px] rounded-[5px] border-0 bg-transparent p-0 text-[15px] font-normal leading-[1.2] text-[#141414] transition-all duration-150 ease-out hover:text-[#623FB5] active:scale-[0.98]"
        >
          <img src={logoutIcon} alt="" className="size-[20px] shrink-0" />
          <span>로그아웃</span>
        </button>
      </div>
    </section>
  );
}
